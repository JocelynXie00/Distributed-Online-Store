# Distributed Online Product Store: Caching, Replication and Fault Tolerance

### Usage:
To run the micro-services on bare metal:

First, `pip3 install grpcio grpcio-tools requests readerwriterlock`<br>
With three terminals:<br>
Then set ip of replicas in `./src/front_end/replica_configuration.txt`, default set as `localhost`
In directory `./src/front_end`: `python3 front_end_server.py` as cache_on mode<br>
								`python3 front_end_server.py <anycharacter>` as cache_off mode
In directory `./src/order`: `python3 order_server.py <1 or 2 or 3>`, <br> where 3 is with highest port number as a beginning leader

In directory `./src/catalog`: `python3 catalog_server.py`


To run the client:<br>
In directory `./src/client`: `python3 client.py <server_ip> <order_probability> <#clients>`

To run the tests:<br>
In directory `./src/test`:<br>
You need to follow the instructions printed by `python3 test.py`.<br>
to kill some replica.


To check on-disk data:<br>
Catalog data is saved in`./src/catalog/catalog.json`. Order number and order log are save in `./src/order/order_number{i}.txt` and `./src/order/order_log{i}.csv`.
where `i = 1/2/3`.
