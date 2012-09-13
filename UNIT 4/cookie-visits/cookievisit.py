import os
import webapp2
import hashlib
import jinja2 
from google.appengine.ext import db 

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir), autoescape = True)

def hash_str(s):
        return hashlib.md5(s).hexdigest()

def make_secure_val(s):
        return "%s|%s" % (s, hash_str(s))

def check_secure_val(h):
        val = h.split('|')[0]
        if h == make_secure_val(val):
                return val


class Handler(webapp2.RequestHandler):
	def write(self, *a, **kw):
		self.response.out.write(*a, **kw)

	def render_str(self, template, **params):
		t = jinja_env.get_template(template)
		return t.render(params)

	def render(self, template, **kw):
		self.write(self.render_str(template, **kw))


class MainPage(Handler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		visiting = 0
		visit_cookie_str = self.request.cookies.get('visiting')
                if visit_cookie_str:
                        cookie_val = check_secure_val(visit_cookie_str)
                        if cookie_val:
                                visiting = int(cookie_val)
		
		visiting += 1
		
		new_cookie_str = make_secure_val(str(visiting))
		self.response.headers.add_header('Set-Cookie', 'visiting=%s; Path=/' % new_cookie_str)
                
            
		if visiting > 10:
			self.write("You are our special guest!!")
		else:
			self.write("You've been here %s times!!" %visiting)

app = webapp2.WSGIApplication([('/', MainPage)], debug=True)
