from web_frame import MyFrame
import grpc
import json
from sys import argv
import signal
from readerwriterlock import rwlock
import requests

from catalog_pb2 import QueryRequest, QueryResponse
from catalog_pb2_grpc import CatalogServiceStub
from order_pb2_grpc import OrderServiceStub
from order_pb2 import OrderNumber, RecoveryInfo, OrderInfo, Empty

# instanciate a webframe app
app = MyFrame()

# since our micro-services would run on the same instance
# we could hard code ip address
catalog_addr = 'localhost:12347'
# default order_addr is localhost
with open('replica_configuration.txt','r') as f:
  addr = f.readlines()
order_addr = [addr[0].split('\n')[0]+':12350', addr[1].split('\n')[0]+':12349', addr[2].split('\n')[0]+':12348']
print("replicas are:", order_addr)
# build grpc stub for catalog and order services
catalog_channel = grpc.insecure_channel(catalog_addr)
catalog_stub = CatalogServiceStub(catalog_channel)

#order_channels = grpc.insecure_channel('localhost:12349') 
#order_stub = OrderServiceStub(order_channels)

order_channels = [grpc.insecure_channel(x) for x in order_addr]
order_stubs = [OrderServiceStub(x) for x in order_channels]

# start a order_leader selection
def select_order_leader():
  order_leader = None
  for stub in order_stubs:
    try:
      response = stub.ping(Empty())
    except grpc.RpcError as e:
      pass
    else:
      order_leader = stub 
      break
  return order_leader

order_leader = select_order_leader()
print(order_leader)

products = ['tux', 'bird', 'elephant', 'whale', "barbie", "lego", "yo-yo", "frisbee", "monopoly", "tinkertoy"]
#initialize a rw lock for each kind of product for effiency
product_cache = {}
for p in products:
  product_cache[p] = [None,rwlock.RWLockFairD()]
cache_on = 1

# input any argument for cache-off mode
if len(argv) == 2:
  cache_on = 0
  print("cache_off")

# register query service with such url pattern/GET
# send a grpc to the catalog server to query the info of the product
# return a json str
@app.route('/products/<product_name>')
def query_response(product_name):
  # product in cache, read price from cache
  # for synchronization, need to use read lock here
  global cache_on
  if cache_on and product_name in product_cache:
    with product_cache[product_name][1].gen_rlock():
      if product_cache[product_name][0]!=None:
        print('cached!')
        price, quantity = product_cache[product_name][0]
        return json.dumps({'data':{'name':product_name,'price':price,'quantity':quantity}})

  # query with error handling
  try:
    response = catalog_stub.query(QueryRequest(name=product_name))

  # if any needed server is not working, raise grpc.RpcError
  except grpc.RpcError as e:
    return json.dumps({"error":{'code': 404,'message':f'gRPC Connection Failed'}})
  # if the product name is invalid,
  if response.quantity == -1:
    return json.dumps({"error":{'code': 404,'message':f'Product {product_name} Not Found'}})

  # get response, cache it
  # for synchronization, need to use write lock here
  price = float('%.2f' % (response.price))
  if cache_on:
    with product_cache[product_name][1].gen_wlock():
      product_cache[product_name][0] = (price, response.quantity)

  # return json to client
  return json.dumps({'data':{'name':product_name,'price':price,'quantity':response.quantity}})

@app.route('/orders',method='POST')
def order_response(order):
  global order_leader
  error = 0
  try:
    order = json.loads(order)
    if order['quantity'] < 1:
      return json.dumps({"error":{'code': 404,'message':f'Must buy at least one product'}})
    if order_leader == None:
      order_leader = select_order_leader()
      if order_leader == None:
        return json.dumps({"error":{'code': 404,'message':f'gRPC Connection Failed'}})
    response = order_leader.buy(OrderInfo(name=order['name'], quantity=order['quantity']))
  

  # Error Handling
  # if any needed server is not working, raise grpc.RpcError
  except grpc.RpcError as e:
    order_leader = select_order_leader()
    if order_leader == None:
      return json.dumps({"error":{'code': 404,'message':f'gRPC Connection Failed'}})
    response = order_leader.buy(OrderInfo(name=order['name'], quantity=order['quantity']))


  # Incorrect json
  except json.decoder.JSONDecodeError as e:
    return json.dumps({"error":{'code': 404,'message':f'Invalid json'}})
  except TypeError as e:
    return json.dumps({"error":{'code': 404,'message':f'Invalid TYPE in key or value'}})
  except KeyError as e:
    return json.dumps({"error":{'code': 404,'message':f'KEY with NAME or QUANTITY Not Found'}})
  

  # if the product is found, but the stock is not sufficient for order,
  if response.order_number == -1:
    return json.dumps({"error":{'code': 404,'message':f'Insufficient Stock'}})
  # if the product name is invalid,
  if response.order_number == -2:
    return json.dumps({"error":{'code': 404,'message':f'Product {order["name"]} Not Found'}})
  
  return json.dumps({"data":{"order_number":response.order_number}})

# Use POST to remove cache of <product_name>
# where POST body is a secret key
# to prevent malicious removing
# use write lock to protect synchronization
@app.route('/remove_cache/<product_name>', method='POST')
def remove_cache(post_body, product_name):
  global cache_on
  if cache_on:
    if post_body != "secret":
      return json.dumps({"error":{'code': 404,'message':f'password incorrect cannot remove cache'}})
    if not(product_name in product_cache):
      return json.dumps({"error":{'code': 404,'message':f'password incorrect cannot remove cache'}})
    with product_cache[product_name][1].gen_wlock():
      product_cache[product_name][0] = None
      return json.dumps({"success":{'code': 200,'message':f'successfully remove {product_name} in cache'}})
 
@app.route('/orders/<order_number>', method='GET')
def query_order(order_number):
  global order_leader
  try:
    order_number = int(order_number)
    response = order_leader.query(OrderNumber(order_number=order_number))
  except grpc.RpcError as e:
    # repeat leader selection even grpcerror since it could recover here.
    order_leader = select_order_leader()
    if order_leader == None:
      return json.dumps({"error":{'code': 404,'message':f'gRPC Connection Failed'}})
    response = order_leader.query(OrderNumber(order_number=order_number))
  if response.order_number == -1:
    return json.dumps({"data":{"order_number":response.order_number}})
  return json.dumps({"data":{"name":response.name, "quantity":response.quantity, "order_number":response.order_number}})


def handler(signum, frame):
  exit()
signal.signal(signal.SIGTERM, handler)
app.run(ip='0.0.0.0', port=12346)
'''
a = QueryRequest(name='tux')
r = catalog_stub.query(a)
print(r.price,r.quantity)
'''