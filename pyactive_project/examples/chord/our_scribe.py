"""
Author: Edgar Zamora Gomez  <edgar.zamora@urv.cat>
"""

from chord_protocol import Node, update, k, betweenE, MAX
from pyactive.controller import init_host, serve_forever, start_controller, interval
from pyactive.exception import TimeoutError

import random

I ={}

def id(MAX):
    # Returns a random number between 0 y 2^k (64)
    return int(random.uniform(0, MAX))

""" Uniform distribution of identifiers across the identifier space"""
def uniform(N, I, max):
    sample = []
    for next in range(N):
        tmp_id = id(max)
        # We are looking for an ID which does not exist in the network, because could happen that
        # the random function gives us an existing value.
        while tmp_id in I:
            tmp_id = id(max)  
        # Once we are sure the value is unique, we store it in the identifier space dictionary
        I[tmp_id] = tmp_id
        # We add it to the list where we have the N identifiers of the uniformly found nodes
        sample.append(tmp_id)  
    return sample

class ScribeNode(Node):
    
    _sync = {'init_node':'1', 'successor':'2','find_successor':'5', 'get_predecessor':'2','closest_preceding_finger':'2'
             ,'closest_preceding_fingerE':'3','join':'20','get_finger':'2', 'is_alive':'2','subscribe':'1','get_my_topics':'5', 
             'get_routing_topic_nodes':'2','lookup_subscribe':'5'}
    _async = ['set_predecessor','remove_son','subscribe_owner','publish','unsubscribe','set_parent', 'set_successor', 'show_finger_node',
               'stabilize', 'notify', 'fix_finger','set_my_topics', 'del_my_topics','leave']
    _ref = ['set_predecessor','remove_son','subscribe','set_parent','lookup_subscribe','publish','unsubscribe', 'get_predecessor', 
            'successor', 'find_successor','get_finger','closest_preceding_finger','closest_preceding_fingerE','subscribe_owner', 'join', 
            'set_successor','notify']
    _parallel = ['stabilize', 'fix_finger']
    
    def __init__(self):
        super(ScribeNode, self).__init__()
        self.my_topics = {}            
        self.routing_topic_nodes = {}   
        self.parent_node = None
        
    def set_parent(self, parent):
        self.parent_node = parent
        
    def get_routing_topic_nodes(self):
        return self.routing_topic_nodes.copy()
    
    def remove_son(self, id, value):
        self.routing_topic_nodes.get(id).remove(value)
        
    def set_my_topics(self, id, value):
        self.my_topics[id] = value
        
    def get_my_topics(self):
        return self.my_topics
    
    def del_my_topics(self, id):
        del self.my_topics[id]
    
    def closest_preceding_fingerE(self, id):
        for i in range(k-1,-1,-1):
            if betweenE(int(self.finger[i].get_id()), int(self.id), id):
                return self.finger[i]
        return self.proxy
    
    def lookup_subscribe(self, id, source):
        first_node = source
        if betweenE(id, int(self.predecessor.get_id()), int(self.id)):
            self.subscribe_owner(id, source, first_node)
            return self.proxy
        n = self.proxy
        
        while not betweenE(id, int(n.get_id()), int(n.successor().get_id())):
            n = n.closest_preceding_fingerE(id)    
            if int(n.get_id()) == id:
                n.subscribe_owner(id, source, first_node)
                return n           
            #Call to introduce some functionality in each forwarder ;) 
            if n != None:  
                source = n.subscribe(id, source)
        
        n.successor().subscribe_owner(id, source, first_node)
        return n.successor()
    
    def subscribe(self, topic, source):   #Subscribe
            
        if ((topic in self.routing_topic_nodes.keys()) and (source not in self.routing_topic_nodes.get(topic))):
            self.routing_topic_nodes.get(topic).append(source)
        else:
            self.routing_topic_nodes[topic] = [source]
        print 'Forward: Source id: ' + str(source.get_id()) + ' --> Node id: ' + str(self.id) + ' (Hash Topic: ' + str(topic) + ')'
        
        print source
        #Change message information for next node.
        source.set_parent(self.proxy)
        return self.proxy               
            

    def subscribe_owner(self, topic, source, first_node): #Subscribe

        if ((topic in self.routing_topic_nodes.keys()) and (source not in self.routing_topic_nodes.get(topic))):    
            self.routing_topic_nodes.get(topic).append(source)
        else:
            self.routing_topic_nodes[topic] = [source]
            
        first_node.set_my_topics(topic, self.id)                        
        print 'Deliver: Source id: ' + str(source.get_id()) + ' --> Node id: ' + str(self.id) + ' (Hash Topic: ' + str(topic) + ')'
        source.set_parent(self.proxy)
    
    def publish(self, topic, msg):            
        print 'id',self.id,'keys',  self.my_topics.keys()
        if (topic in self.my_topics.keys()):
            print 'Node ' + str(self.id) + ' receives the message ' + str(msg)
        print 'id',self.id,'keys',  self.routing_topic_nodes.keys()    
        if (topic in self.routing_topic_nodes.keys()):
            for node in self.routing_topic_nodes.get(topic):
                print node
                node.publish(topic, msg)
                
    def unsubscribe(self, topic, source, first_node):             #Unsubscribe
            
        if ((topic not in self.my_topics.keys()) or (first_node.get_id() == self.id)):
            if ((topic in self.parent_node.get_routing_topic_nodes().keys()) and 
                (source in self.parent_node.get_routing_topic_nodes().get(topic))):
                
                #Clear my node from path of my father
                self.parent_node.remove_son(topic, source)
                print 'Deliver: Source id: ' + str(source.get_id()) + ' --> Node id: ' + str(self.parent_node.get_id()) + ' (Msg id: ' + str(topic) + ')'
        
                if (len(self.parent_node.get_routing_topic_nodes().get(topic)) == 0):
                    if (self.parent_node.get_id() != first_node.get_my_topics(topic)[0]):
                        self.parent_node.unsubscribe(topic, self.parent_node, first_node)
                    else:
                        first_node.del_my_topics(topic)
                        
        print 'Unsubscribed successfully'
        
               
def menu(host, nodes_h, num_nodes):
    fin = False
    while (fin == False):
        print ("-------------Menu-----------------")
        print ("1 - Subscribe to a topic")
        print ("2 - Unsubscribe a topic")
        print ("3 - Publish a message")
        print ("4 - Show Finger Table")
        print ("5 - Leave Node of Chord")
        print ("6 - Exit")
        op = int(raw_input("Choose an option: "))
        if (op==1):     #Subscribe to a topic
            nod = int(raw_input("Choose a node: "))
            try:
                src = nodes_h[nod]
                top = raw_input("Topic's name to subscribe: ")
                key = hash(top)%MAX
                src.lookup_subscribe(key, src)
            except:
                print "Try again!"
                
        elif (op==2):   #Unsubscribe a topic
            nod = int(raw_input("Choose a node: "))
            src = nodes_h[nod]
            top = raw_input("Topic's name to unsubscribe: ")
            key = hash(top)%MAX
            src.unsubscribe(key, src, src)
            
        elif (op==3): #Publish a message
            nod = int(raw_input("Choose a node: "))
            src = nodes_h[nod]
            top = raw_input("Topic's name to publish: ")
            key = hash(top)%MAX 
            msg = raw_input("Write the message: ")
            topics = src.get_my_topics()
            try:
                topics = topics.get(key)
                node_responsible = nodes_h[int(topics[0])-1]   
                print node_responsible.get_id()
                node_responsible.publish(key, msg) 
            except:
                print "This node hasn't this topic"
        elif (op==4):
            nod = int(raw_input("Choose a node: "))
            src = nodes_h[nod]
            src.show_finger_node()
        elif (op==5):
            nod = int(raw_input("Chose a node: "))
            src = nodes_h[nod]
            src.leave()
        
        elif (op==6):
            print 'Exit'
            host.shutdown()
            fin = True
            
        else:
            None          
def start_node():            
    nodes_h = {}
    num_nodes = 10
    retry = 0
    index=0
    tcpconf = ('tcp', ('127.0.0.1', 1238))
    host = init_host(tcpconf)
#    momconf = ('mom',{'name':'s1','ip':'127.0.0.1','port':61613,'namespace':'/topic/test'})
#    host = init_host(momconf)
    sample = uniform(num_nodes, I, MAX)
    print sample
    for i in range(num_nodes):
        nodes_h[i] = host.spawn_id(str(sample[i]), 'our_scribe', 'ScribeNode', [])
    for i in range(num_nodes):    
        nodes_h[i].init_node()
    
    while index < num_nodes:
        try:
            if(nodes_h[index].join(nodes_h[0])):
                print "True"
            interval(5, update, nodes_h[index])
            index += 1
            retry = 0
#            sleep(0.2)
        except TimeoutError:
            retry += 1
            if retry > 3:
                index += 1
    num_nodes -= 1
    "Lookup test"
    menu(host, nodes_h, num_nodes)
    
def start_remote_node():
    nodes_h = {}
    num_nodes = 10
    cont = 11
    retry = 0
    index=0
#    tcpconf = ('tcp', ('127.0.0.1', 6377))
#    host = init_host(tcpconf)
    momconf = ('mom',{'name':'c1','ip':'127.0.0.1','port':61613,'namespace':'/topic/test'})
    host = init_host(momconf)
    for i in range(num_nodes):
        nodes_h[i] = host.spawn_id(str(cont), 'scribe', 'ScribeNode', [])
        cont += 1
    for i in range(num_nodes):    
        nodes_h[i].init_node()
    remote_aref = 'mom://s1/scribe/ScribeNode/1'   
#    remote_aref = 'atom://127.0.0.1:1432/chord/Node/2'
    remote_node = host.lookup(remote_aref)

    while index < num_nodes:
        try:
            if(nodes_h[index].join(remote_node)):
                print "True"
            interval(5, update, nodes_h[index])
            index += 1
            retry = 0
        except(TimeoutError):
            retry += 1
            print 'Timeout Error: Attempts '+retry
            if retry > 3:
                index += 1
    menu(host, nodes_h, num_nodes)
    
def main():
    start_controller('pyactive_thread')
    serve_forever(start_node)
if __name__ == "__main__":
    main() 
