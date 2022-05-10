from http.server import HTTPServer, BaseHTTPRequestHandler
import re
import time, threading
import json
from socketserver import ThreadingMixIn
from concurrent import futures

##########################################################################
# A flask-like web frame (define service via decorator outside the class)#
# Usage:                                                                 #
# frame = MyFrame()                                                      #
# @frame.route('/hello/<name>','POST')                                   #
# def hello(post_body, name):                                            #
#   return f'hello {name}, you post {post_body}'                         #
# frame.run()                                                            #
# if one send a HTTP POST request to                                     #
# [the domain name or IP:port of the server]/hello/cs677                 #
# with POSTBODY "LAB2"                                                   #
# the response on browser is "hello cs677, you post LAB2"                #
##########################################################################
class MyFrame:
  def __init__(self):
    # two kinds of routes
    self.get_path = []
    self.post_path = []

  # sub <name> to (?P<name>.+)
  def build_pattern(self, path):
    pattern = re.sub(r'(<\w+>)', r'(?P\1.+)', path)
    return re.compile(f'^{pattern}$')

  # this is flask type decorator
  # register request url pattern and response method 
  def route(self, path, method='GET'):
    def wrap(f):
      pattern = self.build_pattern(path)
      if method == 'GET':
        self.get_path.append((pattern, f))
      elif method == 'POST':
        self.post_path.append((pattern, f))
      else:
        raise NotImplementedError
      return f
    return wrap

  # find the pattern and serve function from a given path
  def find_pattern_method(self, path, method='GET'):
    if method == 'GET':
      serve_list = self.get_path
    elif method == 'POST':
      serve_list = self.post_path
    else:
      return None 
    for pattern, method in serve_list:
      is_match = pattern.match(path)
      if is_match:
        return method, is_match.groupdict()
    return None 

  # find serve function by url and method
  def serve(self, path, method='GET',body=''):
    result = self.find_pattern_method(path, method)
    if result:
      f, kw = result
      if method == 'GET':
        return f(**kw)
      elif method == 'POST':
        return f(body.decode('utf-8'),**kw)
    else:
      return json.dumps({"error":{'code': 404,'message':'URL Not Found'}})


  def run(self, ip='localhost', port=12346):
    # bind our serve function to handler
    HTTPRequestHandler.serve = self.serve
    ThreadingServer((ip, port), HTTPRequestHandler).serve_forever()



# a helper class for multithreaded server
class ThreadingServer(ThreadingMixIn, HTTPServer):
  pass


class HTTPRequestHandler(BaseHTTPRequestHandler):
  def do_GET(self):
    self.send_response(200)
    self.end_headers()
    # get serve response and encode to bytes
    response = self.serve(self.path,method='GET').encode('utf-8')
    self.wfile.write(response)
 
    

  def do_POST(self):
    # get POST body
    content_length = int(self.headers['Content-Length'])
    body = self.rfile.read(content_length)
    self.send_response(200)
    self.end_headers()
    # get serve response and encode to bytes
    response = self.serve(self.path, method='POST', body=body).encode('utf-8')
    self.wfile.write(response)




if __name__ == '__main__':
  frame = MyFrame()
  @frame.route('/hello/<name>','POST')
  def hello(post_body, name):
    return f'hello {name}, you post {post_body}'
  frame.run()

