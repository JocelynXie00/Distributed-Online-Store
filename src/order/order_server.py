from concurrent import futures
import grpc
import json
import os.path
import csv
import threading
from readerwriterlock import rwlock
from sys import argv
import signal
from collections import deque

from order_pb2_grpc import OrderServiceServicer, add_OrderServiceServicer_to_server, OrderServiceStub
from order_pb2 import OrderNumber, RecoveryInfo, OrderInfo, Empty
from catalog_pb2 import BuyRequest, BuyResponse
from catalog_pb2_grpc import CatalogServiceStub


class OrderLog:
  def __init__(self, server_id, replicas_stubs):

    # initialize the base (last order num in disk)
    if os.path.exists(f'order_number{server_id}.txt'):
      with open(f'order_number{server_id}.txt','r') as f:
        self.order_base = int(f.readlines()[0])
    else:
      self.order_base = -1

    if not os.path.exists(f'order_log{server_id}.csv'):
      with open(f'order_log{server_id}.csv', 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["order_number", "name", "quantity"])

    self.replicas_stubs = replicas_stubs
    self.server_id = server_id
    self.log = deque()

    # initialize a rwlock
    self.rwlock = rwlock.RWLockFairD()

    #self.recovery(replicas_stubs)
    signal.signal(signal.SIGALRM, self.commit)
    signal.alarm(10)

  def push(self, order_info):
    with self.rwlock.gen_wlock():

      # if pushing data that we already saved onto disk, ignore it
      if order_info.order_number <= self.order_base:
        return -1

      # example 
      # push(67) base is 58 log is [59 60 None None 63] 
      # 67-58-5 = 4 so that we append 4 elements
      # after push log should be [59 60 None None 63 None None None 67]
      #
      # push(62)
      # the for loop won't be executed
      # log[62-58-1=3] = 62
      for i in range(order_info.order_number - self.order_base - len(self.log)):
        self.log.append(None)
      self.log[order_info.order_number - self.order_base - 1] = order_info
    return 0

  def push_new(self, name, quantity):
    with self.rwlock.gen_wlock():
      order_number = len(self.log)+self.order_base+1
      new_order = OrderInfo(name=name,quantity=quantity,order_number=order_number)
      self.log.append(new_order)

      return new_order



  # commit
  def commit(self, signum, frame):
    print("committing....")
    with self.rwlock.gen_wlock():
      changed = 0
      with open(f'order_log{self.server_id}.csv', 'a+', newline='') as file:
        writer = csv.writer(file)
        while self.log and not(self.log[0] is None):
          changed = 1
          l = self.log.popleft()
          writer.writerow([l.order_number, l.name, l.quantity])
          self.order_base += 1
      if changed:
        with open(f'order_number{self.server_id}.txt','w') as file:
          file.write(str(self.order_base))
    signal.alarm(10)

  # when someone recovers, it should read a range of order info to push to it
  def read_log_after(self, order_number):
    r = []
    with self.rwlock.gen_rlock():
      if order_number < self.order_base:
        with open(f'order_log{self.server_id}.csv', 'r') as file:
          reader = csv.DictReader(file)
          for row in reader:
            if int(row['order_number']) > order_number:
              r.append(OrderInfo(name=row['name'],quantity=int(row['quantity']),order_number=int(row['order_number'])))
      
      for info in self.log:
        if info.order_number > order_number:
          r.append(info)
      
      return r 


  # read into database/in memory for order-query
  def lookup(self, order_number):
    with self.rwlock.gen_rlock():
      if order_number <= self.order_base and order_number >= 0:
        with open(f'order_log{self.server_id}.csv', 'r') as file:
          reader = csv.DictReader(file)
          for row in reader:
            if int(row['order_number']) == order_number:
              return OrderInfo(name=row['name'],quantity=int(row['quantity']),order_number=int(row['order_number']))
      elif order_number <= self.order_base+len(self.log):
        return self.log[order_number-self.order_base-1]

      else:
        return OrderInfo(order_number=-1)


  def recovery(self):
    with self.rwlock.gen_rlock():
      recovery_info = []
      for stub in self.replicas_stubs:
        try:
          r = stub.get_recovery_info(OrderNumber(order_number=self.order_base))
          if len(r.infos) > len(recovery_info):
            recovery_info = r.infos

        except grpc.RpcError:
          pass 

    for info in recovery_info:
      self.push(info)




class OrderServicer(OrderServiceServicer):
  def __init__(self, server_id, replicas_stubs,catalog_stub):
    super().__init__()
    self.server_id = server_id
    self.replicas_stubs = replicas_stubs
    self.order_log = OrderLog(server_id, replicas_stubs)
    self.catalog_stub = catalog_stub

  # order service calls catalog stub service and return order_number if catalog success.
  def buy(self, request, context):

    response = self.catalog_stub.buy(BuyRequest(name=request.name, quantity = request.quantity))

    if response.done == 1:
      new_order = self.order_log.push_new(request.name, request.quantity)
      for stub in self.replicas_stubs:
        try:
          stub.update(new_order)
        except grpc.RpcError as e:
          pass
      return OrderNumber(order_number = new_order.order_number)
    # separate insufficient stock and invalid product with different return value
    if response.done == -1:
      return OrderNumber(order_number = -1)
    if response.done == -2:
      return OrderNumber(order_number = -2)

  def query(self, request, context):
    return self.order_log.lookup(request.order_number)

  def update(self, request, context):
    # I am the being updated replica
    self.order_log.push(request)
    return Empty()


  def get_recovery_info(self, request, context):
    infos = self.order_log.read_log_after(request.order_number)
    print(infos)
    r = RecoveryInfo(infos=infos)

    return r
  def ping(self, request, context):
    return Empty()




'''
# stop docker container would signal SIGTERM to each proc
# we need a signal handler to save data when stop docker
def handler(signum, frame):
  with open('order_number.txt','w') as f:
    f.write(str(order))
  periodSave(len(order_log), order_log)
  exit()

signal.signal(signal.SIGTERM, handler)

# save when Ctrl+C (keyboard interrupt) (would signal SIGINT)
signal.signal(signal.SIGINT, handler)

serve()
'''

def main():
  # declare which order server it is
  if len(argv) != 2 or argv[1] not in ['1','2','3']:
    print('usage: python order_server.py <[1-3]>')
    return -1
  # get grpc stub to catalog server
  catalog_addr = 'localhost:12347'
  catalog_channel = grpc.insecure_channel(catalog_addr)
  catalog_stub = CatalogServiceStub(catalog_channel)

  # get other two order servers's stub
  replicas_stubs = []
  with open('../front_end/replica_configuration.txt') as f:
    addr = f.readlines()
  for i in range(1,4):
    if i != int(argv[1]):
      ipaddr = addr[i-1].split('\n')[0]
      replicas_addr = f'{ipaddr}:{12347+i}'
      print(replicas_addr)
      replicas_channel = grpc.insecure_channel(replicas_addr)
      stub = OrderServiceStub(replicas_channel)
      replicas_stubs.append(stub)


  server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
  servicer =  OrderServicer(int(argv[1]), replicas_stubs, catalog_stub)
  add_OrderServiceServicer_to_server(
      servicer, server)
  server.add_insecure_port(f'0.0.0.0:{12347+int(argv[1])}')
  server.start()
  servicer.order_log.recovery()
  server.wait_for_termination()

  
if __name__ == '__main__':
  main()

