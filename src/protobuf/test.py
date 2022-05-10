import grpc
from order_pb2_grpc import OrderServiceServicer, add_OrderServiceServicer_to_server, OrderServiceStub
from order_pb2 import OrderNumber, RecoveryInfo, OrderInfo, Empty
e = Empty()
o = [OrderInfo(name='r',quantity=5),OrderInfo(name='rr',quantity=6),OrderInfo(name='rrr',quantity=7)]
o2 = OrderNumber(order_number=5)
r = RecoveryInfo()
for i in r.infos:
  print(i)

print(r.infos)


replicas_addr = f'localhost:12349'
replicas_channel = grpc.insecure_channel(replicas_addr)
stub = OrderServiceStub(replicas_channel)
r = stub.query(OrderNumber(order_number=0))

print(r.order_number)

'''
from collections import deque
class A:
  def hello(self):
    print("hello")

a = A()
def f(g):
  g()
f(a.hello)
a = deque()
print(a)
'''