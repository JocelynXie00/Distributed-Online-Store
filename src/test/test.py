import requests
import random
from sys import argv
import json
import time
###################################################################
# Usage:                                                          #
# you have to mannually kill server following instructions printed# 
# start three microservices                                       #
# python test_error.py <ip_address>                               #
# It will build one session to front-end server with <ip_address> #
# In session, it will send error query requests and buy request   #
# to check if the server can handle those errors                  #
###################################################################
ip = 'localhost'
if len(argv) == 2:
	ip = argv[1]

s = requests.Session() 
port = 12346
orderURL = 'http://' + ip +':'+str(port)+'/orders'
queryURL = 'http://' + ip +':'+str(port)+'/products/'
products = ['tux', 'bird', 'elephant', 'whale', "barbie", "lego", "yo-yo", "frisbee", "monopoly", "tinkertoy"]

# test 0 restocking
print('test 0: test restock')
try:
	r1 = s.get(queryURL+'tux')
	print(r1.text)
	message = r1.json()
	if "data" in message:
		r = requests.post(orderURL, json.dumps({'name':'tux','quantity':message['data']['quantity']}))
		print('success order', r.json()['data']['order_number'], 'bought tux all')
	time.sleep(10)
	r2 = s.get(queryURL+'tux')
	message = r2.json()
	assert message['data']['quantity'] == 100
	print('PASS! Catalog restocks successfully')
except:
	print('FAIL')
print()

# test 1: work normally
print('test 1: test functionality: query->buy all(sucess)->query (return 0)->buy one(fail)')
try:
	r0 = s.get(queryURL+products[1])
	quantity = r0.json()['data']['quantity']
	r1 = s.post(orderURL, json.dumps({'name':products[1],'quantity':quantity}))
	if ('error' in r1.json()) :
		assert False
	r4 = s.get(orderURL+'/1')
	if 'error' in r4.json():
		assert False
	print(f'PASS! test1 returns\n{r0.text}\n{r1.text}\n{r4.text}')
except:
	print('FAIL!')
print()

# test 2: crash failure test manually 
print('test 2: crash failure test manually, Please turn off the leader order in 10 sec')
time.sleep(10)
try:
	r1 = s.post(orderURL, json.dumps({'name':products[2],'quantity':1}))
	if 'error' in r1.json():
		assert False
	print(f'PASS! test2 returns\n{r1.text}, did not notice order server crash!')
	print('now get the order server back in 10 sec')
	time.sleep(10)
except:
	print('FAIL!')
print()

# test 3: invalid order-query
print('test 3: invalid order-query')
try:
	r = s.get(orderURL+'/10000')
	print(r.text)
	if 'error' in r.json():
		assert False
	assert r.json()['data']['order_number'] == -1
	print('PASS! order number does not exist')
except:
	print('FAIL')
print()

# test 4: data consistency in replica in the end
# give some time for committing and turn off 

print('test 4: data consistency in replica in the end')
print('please turn off order server to write back to database in 10 sec')
time.sleep(10)
consistency = 1
try:
	with open('../order/order_log3.csv') as f:
		log = f.readlines()
	with open('../order/order_log2.csv') as f:
		if f.readlines() != log:
			consistency = 0
	with open('../order/order_log1.csv') as f:
		if f.readlines() != log:
			consistency = 0
	assert consistency == 1
	print("PASS! data in 3 replicas keep the same")
except:
	print('FAIL! data is not consistent')
print()