import requests
import random
import time
from multiprocessing import Pool
from sys import argv
import json
import csv
from requests.exceptions import ConnectionError, Timeout

'''
Usage: python client.py <ip_address> <probability> <number_of_clients>
It will create <number_of_clients> client processes
each will build one session to front-end server with <ip_address>
In each session first query a random product 
and with probability <probability> to send order request

'''

def make_session(ip, p):
  port = 12346
  host = 'http://'+ip+':'+str(port)
  s = requests.Session() # create a session
  products = ['tux', 'bird', 'elephant', 'whale', "barbie", "lego", "yo-yo", "frisbee", "monopoly", "tinkertoy"]
  avg_query_latency = 0
  avg_order_latency = 0
  order_index = 0
  query_index = 0
  orderq_index = 0
  order_record = []
  for n in range(100):
    product = products[random.randint(0, 9)] # randomly select a product
    t0 = time.time()
    r = s.get(host+'/products/'+product) # send query
    t1 = time.time()
    if t1-t0<0.5:
      avg_query_latency += ((t1-t0)*1000 - avg_query_latency) / (query_index + 1)
      query_index+=1
    message = r.json()
    orderIf = 1
    if 'data' in message and message['data']['quantity'] > 0: # if valid
      orderIf = random.uniform(0, 1)
    if orderIf < p: # make an order with probability p
      ordercontent = json.dumps({'name':product, 'quantity':1})
      t0 = time.time()
      r = s.post(host+'/orders', ordercontent)
      t1 = time.time()
      if t1-t0<0.5:
        avg_order_latency += ((t1-t0)*1000 - avg_order_latency) / (order_index + 1)
        order_index += 1
      message = r.json()
      if 'data' in message:
        order_record.append([product, 1, message['data']['order_number']])
      # += ((end - start) * 1000 - latency) / (index + 1)
    avg_order_query_latency = 0
  for i,record in enumerate(order_record):
    t0 = time.time()
    r = s.get(host+'/orders/'+str(record[2]))
    t1 = time.time()
    if t1-t0<0.5:
      avg_order_query_latency += ((t1-t0)*1000 - avg_order_query_latency) / (orderq_index + 1)
      orderq_index+=1
    message = r.json()
    consistency = 1
    if 'data' in message and message['data']['name'] == record[0] and message['data']['quantity'] == record[1]:
      pass
    else:
      print("record", i, " is NOT consistent")
      consistency = 0
      break
  '''
  if consistency==1:
    print("records are consistent") 
  '''
  return avg_query_latency, avg_order_latency, avg_order_query_latency

def wrapper(args):
  return make_session(*args)

if __name__ == '__main__':
  if len(argv) == 4:
    ip = argv[1]
    p = float(argv[2])
    n = int(argv[3])
  else:
    print("Usage: python client.py <server_ip> <order_probability> <#clients>")
    exit(1)
  pool = Pool(processes=10)

  r = pool.map(wrapper ,[[ip,p]]*n)
  avg_q = 0
  avg_b = 0
  avg_o = 0
  for e in r:
    avg_q += e[0]
    avg_b += e[1]
    avg_o += e[2]
  avg_q /= n
  avg_b /= n 
  avg_o /= n 
  print("average query latency:", '%.2f' % (avg_q), "ms\naverage buy latency:", '%.2f' % (avg_b), "ms\naverage order_query latency:", '%.2f' % (avg_o), "ms")

  # check order record consistency
  '''
  for i in range(1,4):
    with open(f'./order/order_log{i}.csv','r') as file:   
      reader = csv.DictReader(file)
      reader = list(reader)
      if len(reader)!= len(order_record):
        print(f'order_log{i} is NOT consistent with client order_record')
        continue
      consistency = 1
      for j,row in enumerate(reader):
        if order_record[j][0] != row['name']:
          print("!!!!!!", j)
          consistency = 0
        if order_record[j][1] != row['quantity']:
          print("??????", j)
          consistency = 0
      if consistency:
        print(f'order_log{i} is CONSISTENT with client order_record')
  '''


