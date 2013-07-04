"""
Author: Edgar Zamora Gomez  <edgar.zamora@urv.cat>
"""
from chord_protocol import Node, k, MAX, between, start_node, update, show
from pyactive.controller import serve_forever, start_controller, init_host, interval
from pyactive.exception import TimeoutError

class Node_chord(Node):
    _sync = {'init_node':'1', 'successor':'2','find_successor':'5', 'get_predecessor':'2','closest_preceding_finger':'2'
             ,'join':'20', 'is_alive':'2','give_successor_list':'5'}
    _async = ['leave','set_predecessor', 'set_successor', 'show_finger_node', 'stabilize', 'notify', 'fix_finger']
    _ref = ['set_predecessor', 'get_predecessor', 'successor', 'find_successor', 'closest_preceding_finger', 'join', 
            'set_successor', 'notify']
    _parallel = ['stabilize', 'fix_finger']
    
    def __init__(self):
        super(Node_chord, self).__init__()
        self.successorList = []
        self.retry = [0,0]
        
    def successor(self):
        return self.successorList[0]
    
    def join(self, n1):
        """if join return false, the node not entry in ring. Retry it before"""
        if self.id == n1.get_id():
            for i in range(k):
                self.finger[i] = self.proxy
                self.successorList.append(self.proxy)
            self.predecessor = self.proxy
            self.run = True
            return True
        else:
            try:
                self.init_finger_table(n1)
            except:
                print 'Join failed'
                return False
            else:
                self.init_successor_list()
                self.run = True
                return True
            
    def init_successor_list(self):
        self.successorList.append(self.finger[0])
        for i in range(k - 1):
            self.successorList.append(self.successorList[i].successor())
            
    def update_list_successor(self):
        try:
            if(self.successorList[0].is_alive()):
                auxList = self.successorList[0].give_successor_list()
                for i in range(k-1):
                    self.successorList[i+1] = auxList[i]
                self.retry[0] = 0
        except(TimeoutError):
            self.retry[0] += 1
            if self.retry[0] > 5:
                self.retry[0] = 0
                self.update_successor()
                
    def update_successor(self):
        searching = True
        while(searching and self.indexLSucc < k):
            n = self.successorList[self.indexLSucc]
            self.indexLSucc += 1
            self.successorList[0] = n
            try:
                if(n.is_alive()):
                    self.set_successor(n)
                    searching = False
            except(TimeoutError): 
                searching = True
        self.indexLSucc = 1
        self.update_list_successor()
           
    def give_successor_list(self):
        return self.successorList[:]
    
    def stablilize(self):
        try:
            x = self.successorList[0].get_predecessor()
            self.retry[1] = 0
        except(TimeoutError):
            self.retry[1] += 1
            if self.retry[1] > 5:
                self.retry[1] = 0
                self.update_successor()
            
        else:
            if(between(int(x.get_id()), int(self.id), int(self.successorList[0].get_id()))):
                self.set_successor(x)
            self.update_list_successor()
            self.successorList[0].notify(self.proxy)
    
    def set_successor(self, succ):
        self.successorList[0] = succ
        super(Node_chord, self).set_successor(succ)
    
    def leave(self):
        print 'bye bye!'
        self.successorList[0].set_predecessor(self.predecessor)
        self.predecessor.set_successor(self.successorList[0])
        self._atom.stop()
        
def start_node():            
    nodes_h = {}
    num_nodes = 20
    cont = 1
    retry = 0
    j = 0
#    tcpconf = ('tcp', ('127.0.0.1', 1432))
#    host = init_host(tcpconf)
    momconf = ('mom',{'name':'s1','ip':'127.0.0.1','port':61613,'namespace':'/topic/test'})
    host = init_host(momconf)
#    log = host.spawn_id('log','chord_log','LogUML',[])
#    host.set_tracer(log)
    for i in range(num_nodes):
        nodes_h[i] = host.spawn_id(str(cont), 'chord_with_succlist', 'Node_chord', [])
        cont += 1
    for i in range(num_nodes):    
        nodes_h[i].init_node()
        
    while j < num_nodes:
        try:
            if(nodes_h[j].join(nodes_h[0])):
                print "True"
            
            interval(5, update, nodes_h[j])
        except TimeoutError:
            retry += 1
            if retry > 3:
                break
        else:
            j += 1
    interval(200, show, nodes_h[0])
    interval(200, show, nodes_h[num_nodes /2])
    interval(200, show, nodes_h[num_nodes -1])

def start_remote_node():
    nodes_h = {}
    num_nodes = 100
    cont = 21 + 50
    retry = 0
    j=0
#    tcpconf = ('tcp', ('127.0.0.1', 6377))
#    host = init_host(tcpconf)
    momconf = ('mom',{'name':'c2','ip':'127.0.0.1','port':61613,'namespace':'/topic/test'})
    host = init_host(momconf)
    for i in range(num_nodes):
        nodes_h[i] = host.spawn_id(str(cont), 'chord_with_succlist', 'Node_chord', [])
        cont += 1
    for i in range(num_nodes):    
        nodes_h[i].init_node()
    remote_aref = 'mom://s1/chord_with_succlist/Node_chord/1'   
#    remote_aref = 'atom://127.0.0.1:1432/chord/Node/2'
    remote_node = host.lookup(remote_aref)

    while j < num_nodes:
        try:
            if(nodes_h[j].join(remote_node)):
                print "True"
            interval(5, update, nodes_h[j])
            j += 1
            retry = 0
        except(TimeoutError):
            retry += 1
            if retry > 3:
                break
    
    interval(200, show, nodes_h[0])
    interval(200, show, nodes_h[num_nodes/2])
    interval(200, show, nodes_h[num_nodes - 1])
def main():
    start_controller('pyactive_thread')
    serve_forever(start_remote_node)
    
if __name__ == "__main__":
    main() 