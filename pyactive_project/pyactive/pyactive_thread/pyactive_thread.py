"""
Author: Edgar Zamora Gomez  <edgar.zamora@urv.cat>
"""

from pyactive.constants import *
from pyactive.exception import PyactiveError, TimeoutError, MethodError, NotFoundDispatcher
from tcp_server import Server
from mom_server import Server as Session
from threading import Thread, Event, RLock,current_thread, Lock
from Queue import Queue
from pyactive.abstract_actor import Abstract_actor
from urlparse import urlparse

import pyactive.controller as controller
import cPickle
import copy
pending = {} 
threads = {}   

    
class Channel(Queue):
    def __init__(self):
        Queue.__init__(self)
    def send(self,msg):
        self.put(msg)
    def receive(self, timeout = None):
        return self.get(timeout=timeout)
    
    
class Actor(Abstract_actor):
    
    def __init__(self):
        Abstract_actor.__init__(self)
        self.__lock = None
        self.channel = Channel()
        
    def __processQueue(self):
        while True:
            message = self.channel.receive()
            if message==StopIteration:
                break
            self.receive(message)
    
    def registry_object(self, obj):
        self.obj = obj
        
    def run(self):
        Abstract_actor.run(self)
        
        self.thread = Thread(target=self.__processQueue)
        self.thread.start()
        threads[self.thread] = self.aref
        
    def stop(self):
        self.channel.send(StopIteration)
    
    def send(self,msg):
        msg[TO] = self.aref
        msg[TYPE] = CALL
        msg[TARGET] = self.target
        if msg[MODE] == SYNC:
            pending[msg[RPC_ID]] = 1
            msg[SRC] = self.channel
        print msg
        self.out.send(msg)
    
    def init_parallel(self):
        '''Create Lock to guarantee concurrency when it uses parallel wrapper. 
        In addition it put parallel wrapper in the correct objects methods'''
        self.__lock = Lock()
        for name in self.parallelList:
            setattr(self.obj, name, ParallelWraper(getattr(self.obj, name), self.aref, self.__lock))

    def receive_result(self, timeout = None):
        '''receive result of synchronous calls'''
        result = self.channel.receive(timeout)
        return result[RESULT]
    
    
    def receive(self,msg):   
        ''' receive messages and invokes object method'''
        invoke = getattr(self.obj, msg[METHOD])
        params = msg[PARAMS]
        result = None
        try:
            if self.__lock != None:
                with self.__lock:
                    result = invoke(*params)
            else:
                result = invoke(*params)
        except PyactiveError,e:
            result= e    
            msg[ERROR]=1  
        except TypeError,e2:
            result = MethodError()
            msg[ERROR]=1
    
        if msg[MODE] == SYNC:
            msg2 = copy.copy(msg)
            target = msg2[SRC]
            msg2[TYPE]= RESULT
            msg2[RESULT]=result
            del msg2[PARAMS]
            del msg2[SRC]
            if pending.has_key(msg[RPC_ID]):
                del pending[msg[RPC_ID]]
                _from = msg2[FROM]
                msg2[FROM] = self.aref
                msg2[TO] = _from
                self.send2(target,msg2)
                
    def get_proxy(self):
        return self.host.load_client(self.channel, self.aref, get_current())
            

class ParallelWraper():
    def __init__(self, send, aref, lock):
        self.__send = send
        self.__aref = aref
        self.__lock = lock
    def __call__(self, *args, **kwargs):
        t1 = Thread(target=self.invoke, args=(self.__send, args, kwargs))
        t1.start()
        threads[t1] = self.__aref
        
    def invoke(self, func, args=[], kwargs=[]):
        with self.__lock:
            func(*args, **kwargs)
        
class TCPDispatcher(Actor):
    """ """
    def __init__(self,host, addr):
        Actor.__init__(self)
        ip, port = addr
        self.name = ip + ':' + str(port)
        self.conn = Server(ip, port, self)
        self.addr = addr
        self.host = host
        
        self.callback = {}
        
    def receive(self,msg):
        if msg[MODE]==SYNC and msg[TYPE]==CALL:
            self.callback[msg[RPC_ID]]= msg[SRC]
        
        msg[SRC] = self.addr
        try:
            self.conn.send(msg)
        except Exception,e:
            print e,'TCP ERROR 2'
             
    def _stop(self):
        self.channel.send(StopIteration)
        self.conn.close()
        
    def is_local(self, name):
        return name == self.name
   
    def on_message(self, msg):
        try:
            if msg[TYPE]==RESULT:
                if pending.has_key(msg[RPC_ID]):
                    del pending[msg[RPC_ID]]
                    target = self.callback[msg[RPC_ID]]
                    del self.callback[msg[RPC_ID]]       
                    target.send(msg)
            else:
                if msg[MODE]== SYNC:
                    msg[TARGET]=msg[SRC]
                    msg[SRC]= self.channel
                    pending[msg[RPC_ID]] = 1
                aref = msg[TO]
                aurl = urlparse(aref)
                self.host.objects[aurl.path].channel.send(msg)
        except Exception,e:
            print e,'TCP ERROR 1'
class MOMDispatcher(Actor):
                    #,ConnectionListener):

    def __init__(self, host, conf):
        Actor.__init__(self)
        momip = conf[IP]
        momport = conf[PORT]
        self.namespace = conf[NAMESPACE]
        self.session = Session(momip,momport)
        self.host = host
        self.name = conf[NAME]
        self.session.subs(self,self.namespace,{'selector':"HOST='%s'"%self.name})
        self.callback = {}

        
    def receive(self,msg):
        if msg[MODE]==SYNC and msg[TYPE]==CALL:
            self.callback[msg[RPC_ID]]= msg[SRC]
            del msg[SRC]
        parsed_msg = cPickle.dumps(msg)
        try:
            self.session.pub(parsed_msg,self.namespace,{'HOST':msg[TARGET],SRC:self.name})
        except Exception,e:
            print e,'MOM ERROR'
            
    def is_local(self,name):
        return name == self.name
    
    #@async
    def _stop(self):
        self.session.close()
        super(MOMDispatcher,self)._stop()
        
    
    def on_message(self, headers, message):
        try:
            msg = cPickle.loads(message)
            if msg[TYPE]==RESULT:
                if pending.has_key(msg[RPC_ID]):
                    del pending[msg[RPC_ID]]
                    target = self.callback[msg[RPC_ID]]
                    del self.callback[msg[RPC_ID]]
                    target.send(msg)
            else:
                if msg[MODE]== SYNC:
                    msg[SRC]= self.channel
                    msg[TARGET]=headers[SRC]
                    pending[msg[RPC_ID]] = 1
                aref = msg[TO]
                aurl = urlparse(aref)
                self.host.objects[aurl.path].channel.send(msg)
        except Exception,e:
            pass
        
def new_MOMdispatcher(host, dir):
    mom = MOMDispatcher(host, dir)
    mom.run()
    return mom
            
def new_TCPdispatcher(host, dir):
    tcp = TCPDispatcher(host, dir) 
    tcp.run()
    return tcp

def new_dispatcher(host, transport):
    dispatcher_type = transport[0]
    if dispatcher_type == TCP:
        return new_TCPdispatcher(host, transport[1])
    if dispatcher_type == MOM:
        return new_MOMdispatcher(host, transport[1])
    else:
        raise NotFoundDispatcher()
           
def get_current():
    current = current_thread()
    if threads.has_key(current):
        return threads[current] 
                
def send_timeout(channel,rpc_id):
    if pending.has_key(rpc_id):
        del pending[rpc_id]
        msg = {}
        msg[TYPE] = ERROR
        msg[RESULT] = TimeoutError()
        channel.send(msg)
    
def launch(func, params=[]):
    t1 = Thread(target=func, args=params)
    threads[t1] = 'atom://localhost/'+func.__module__+'/'+func.__name__
    t1.start()
    t1.join()
    host =  controller.get_host()
    host._shutdown()
        
def serve_forever(func, params=[]):
    threads[current_thread()] = 'atom://localhost/'+func.__module__+'/'+func.__name__
    func(*params)
    