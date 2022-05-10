from concurrent import futures
import grpc
from catalog_pb2_grpc import CatalogServiceServicer, add_CatalogServiceServicer_to_server
from catalog_pb2 import QueryRequest, QueryResponse, BuyRequest, BuyResponse
import json
from readerwriterlock import rwlock
import signal
from threading import Timer
import requests
from sys import argv
# declare rwlock, implement query and buy with reader and writer lock respectively
rw = rwlock.RWLockFairD()
cache_on = 1
if len(argv) == 2:
  print("cache off")
  cache_on = 0
# declare a global variable catalog and read the file
with open('catalog.json','r') as f:
  catalog = json.load(f)

# push remove cache to front-end server
def push(product_name):
  requests.post(f'http://localhost:12346/remove_cache/{product_name}','secret')



class CatalogServicer(CatalogServiceServicer):
  def __init__(self):
    super().__init__()

  def query(self, request, context):
    with rw.gen_rlock():
      quantity, price = catalog.get(request.name, (-1,0))
      return QueryResponse(quantity=quantity, price=price)

  def buy(self, request, context):
    with rw.gen_wlock():
      quantity, price = catalog.get(request.name, (-1,0))
      # if the product name is invalid, return done as -2
      if quantity == -1:
        return BuyResponse(done = -2)
      if quantity >= request.quantity:
        catalog[request.name][0] -= request.quantity
        global cache_on
        if cache_on:
          push(request.name)
        return BuyResponse(done = 1)
      # if the stock is not sufficient for this order, return done as -1
      return BuyResponse(done = -1)




def serve():
  # start a server with a thread_pool
  server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
  add_CatalogServiceServicer_to_server(
      CatalogServicer(), server)
  server.add_insecure_port('0.0.0.0:12347')
  server.start()
  server.wait_for_termination()

# stop docker container would signal SIGTERM to each proc
# we need a signal handler to save data when stop docker
def handler(signum, frame):
  with open('catalog.json','w') as f:
    json.dump(catalog, f)
  exit()

def refresh(signum, frame):
  with rw.gen_wlock():
    for product, info in catalog.items():
      if info[0] == 0:
        catalog[product][0] = 100
        global cache_on
        if cache_on:
          push(product)
  signal.alarm(10)

signal.signal(signal.SIGALRM, refresh)
signal.alarm(10)

signal.signal(signal.SIGTERM, handler)

# save when Ctrl+C (keyboard interrupt) (would signal SIGINT)
signal.signal(signal.SIGINT, handler)
serve()
