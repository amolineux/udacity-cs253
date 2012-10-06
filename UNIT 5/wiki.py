import os
import re
import random
import hashlib
import hmac
from string import letters
import logging
import json
import webapp2
import jinja2
import time

from google.appengine.ext import db
from google.appengine.api import memcache 

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = False)    
jinja_env_escaped = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir), autoescape = True)

#password hash using salt
def make_salt(length = 5):
    return ''.join(random.choice(letters) for x in range(length))

def make_pw_hash(name, pw, salt = None):
    if not salt:
        salt = make_salt()
    h = hashlib.sha256(name + pw + salt).hexdigest()
    return '%s,%s' % (salt, h)

def valid_pw(name, password, h):
    salt = h.split(',')[0]
    return h == make_pw_hash(name, password, salt)



#cookie hashing and hash-validation functions
secret = 'weneverwalkalone'

def make_secure_cookie(val):
    return '%s|%s' % (val, hmac.new(secret, val).hexdigest())

def check_secure_val(secure_val):
    val = secure_val.split('|')[0]
    if secure_val == make_secure_cookie(val):
        return val

def render_str(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)       



#blog handler
class BlogHandler(webapp2.RequestHandler):
    	def write(self, *a, **kw):
		self.response.out.write(*a, **kw)

	def render_str(self, template, **params):
		t = jinja_env.get_template(template)
		return t.render(params)

	def render_str_escaped(self, template, **params):
		t = jinja_env_escaped.get_template(template)
		return t.render(params)

	def render(self, template, **kw):
		self.write(self.render_str(template, **kw))

	def render_content(self, template, **kw):
		content = self.render_str(template, **kw)
		self.render("index.html", content=content, user=self.get_logged_in_user(), **kw)
	
	def is_logged_in(self):
		user_id = None
		user = None
		user_id_str = self.request.cookies.get("user_id")
		if user_id_str:
			user_id = check_secure_val(user_id_str)
		return user_id

	
    	def get_logged_in_user(self):
		user_id = self.is_logged_in()
		user = None
		if user_id:
			user = User.get_by_id(long(user_id))
		return user 	
    



#welcome handler
class Welcome(BlogHandler):
     
  def get(self):
     cookie_val = self.request.cookies.get("user_id")#In this case we will get the value of key(in this case name) 
     
     if cookie_val: 
	user_id = check_secure_val(str(cookie_val))	
        u = User.get_by_id(int(user_id))
        
        self.render("welcome.html", username = u.username)
     else:
        self.redirect("/signup")



# class for blog-post(subject and content) entries
class Post(db.Model):	
	subject = db.StringProperty(required = True)
	content = db.TextProperty(required = True)
	created = db.DateTimeProperty(auto_now_add = True)
        last_modified = db.DateTimeProperty(auto_now = True)

	def render(self):
        	self._render_text = self.content.replace('\n', '<br>')
        	return render_str("post.html", p = self)

        
# class for user entries
class User(db.Model):
	username = db.StringProperty(required = True)
	password = db.StringProperty(required = True)
	email = db.StringProperty(required = False)
	


# RegEx for the username field
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
PASSWORD_RE = re.compile(r"^.{3,20}$")
EMAIL_RE = re.compile(r"^[\S]+@[\S]+\.[\S]+$")

# Validation for Usernames
def valid_username(username):
	return USERNAME_RE.match(username)
def valid_password(password):
	return PASSWORD_RE.match(password)
def valid_email(email):
        return not email or EMAIL_RE.match(email)




#handler for signup
class Signup(BlogHandler):
        
    def get(self):
	 self.render_content("signup.html")	

    def post(self):
        have_error    =	False
        user_name     = self.request.get('username')
        user_password = self.request.get('password')
        user_verify   = self.request.get('verify')
        user_email    = self.request.get('email')

        
        name_error = password_error = verify_error = email_error = ""

        if not valid_username(user_name):
            name_error = "That's not a valid username"
	    have_error = True

        if not valid_password(user_password):
            password_error = "That's not a valid password"
            have_error = True 

        elif user_password != user_verify:
            verify_error = "Your passwords didn't match"
            have_error = True

        if not valid_email(user_email):
            email_error = "That's not a valid email"
            have_error = True
  
        if have_error:
		
		self.render_content("signup.html"
				, username=user_name
				, username_error=name_error
				, password_error=password_error
				, verify_error=verify_error
				, email=user_email
				, email_error=email_error)
        else:      
           
      	   
      	   u = User.gql("WHERE username = '%s'"%user_name).get()
           	   
           if u:
            	name_error = "That user already exists."
            	self.render_content("signup.html")
           else:
            # make salted password hash
            	h = make_pw_hash(user_name, user_password)
		u = User(username=user_name, password=h,email=user_email)
		
            	u.put()
                uid= str(make_secure_cookie(str(u.key().id()))) #dis is how we get the id from google data store(gapp engine)
		#The Set-Cookie header which is add_header method will set the cookie name user_id(value,hash(value)) to its value
		self.response.headers.add_header("Set-Cookie", "user_id=%s; Path=/" %uid)
		self.redirect("/welcome")


#login handler
class Login(BlogHandler):
    
    def get(self):
        self.render_content("login-form.html")
	
        
    def post(self):
        user_name = self.request.get('username')
        user_password = self.request.get('password')
        			
			
        u = User.gql("WHERE username = '%s'"%user_name).get()
                
	if u and valid_pw(user_name, user_password, u.password):
           uid= str(make_secure_cookie(str(u.key().id())))
           self.response.headers.add_header("Set-Cookie", "user_id=%s; Path=/" %uid)
	   self.redirect('/')          
			
        else:
            msg = "Invalid login"
            self.render_content("login-form.html", error = msg)	
	    


#logout handler
class Logout(BlogHandler):
    def get(self):
        self.response.headers.add_header("Set-Cookie", "user_id=; Path=/")
        self.redirect("/signup")


def top_posts(update = False):	
	posts = memcache.get("top")
	if posts is None or update:
		posts = db.GqlQuery("SELECT * FROM Post ORDER BY created DESC LIMIT 10")
		posts = list(posts) # to avoid querying in iterable
		memcache.set("top", posts)
		memcache.set("top_post_generated", time.time())
	return posts



#main page
class MainPage(BlogHandler):
  	def get(self):
		# posts = db.GqlQuery("SELECT * FROM Post ORDER BY created DESC LIMIT 10")
		# caching for query above
		posts = top_posts()
		diff = time.time() - memcache.get("top_post_generated")
		self.render_content("front.html", posts=posts, time_update=str(int(diff)))




def get_post(key): # cache function same as above but this one is for particular post
	post = memcache.get('post')
	if post and key == str(post.key().id()):
		return post
	else:
		post = Post.get_by_id(int(key))
		memcache.set('post', post)
		memcache.set('post-generated', time.time())
		return post



# Handler for a specific Entry
class SpecificPostHandler(BlogHandler):	
	def get(self, key):
		post = get_post(key)
	
		diff = time.time() - memcache.get('post-generated')
		diff_str = "Queried %s seconds ago"%(str(int(diff)))
		self.render_content("permalink.html", post=post, time_update=diff_str)


# Handler for posting newpoHandler for a specific Wiki Page Entrysts
class EditPageHandler(BlogHandler):	
	
	def get(self):
		if self.is_logged_in():	       
			post = top_posts()		   	
			self.render_content("newpost.html", post=post)
            	else:
			self.redirect("/login")


	def post(self):
		if self.is_logged_in():                
			subject = self.request.get("subject") 			
			content = self.request.get("content")
			if subject and content:
				p = Post(subject=subject, content=content)
				p.put()
				KEY = p.key().id()
				top_posts(update = True)
				self.redirect("/"+str(KEY), str(KEY))
			else:
				error = "subject and content, please!"
				self.render_content("newpost.html", subject=subject, content=content, error=error)	
		else:
			self.redirect("/login")

			
# /.json gives json of last 10 entries
class JsonMainHandler(BlogHandler): 
	def get(self):
		self.response.headers['Content-Type']= 'application/json; charset=UTF-8'
		posts = db.GqlQuery("SELECT * FROM Post ORDER BY created DESC LIMIT 10")
		posts = list(posts)
		js = []
		for p in posts:#json libraries in python excepts data types dat nos how 2 convert in json which're list,dict..
			d = {'content': p.content, 'subject': p.subject, 'created': (p.created.strftime('%c')), 
			     'last_modified': (p.created.strftime('%c'))}
			js.append(d)#so created dictionary representation n later passed into json   
		self.write(json.dumps(js))#json representation using dumps


# /post-id.json gives json of that specific post
class JsonSpecificPostHandler(BlogHandler): 
	def get(self, key):
		self.response.headers['Content-Type']= 'application/json; charset=UTF-8'
		p = Post.get_by_id(int(key))
		d = {'content': p.content, 'subject': p.subject, 'created': (p.created.strftime('%c')), 
		     'last_modified': (p.created.strftime('%c'))}
		self.write(json.dumps(d))




class FlushHandler(BlogHandler):	
	def get(self):
		memcache.flush_all()
		self.redirect('/')
		

PAGE_RE = r'(/(?:[a-zA-Z0-9_-]+/?)*)'
app = webapp2.WSGIApplication([('/', MainPage),('/edit', EditPageHandler),
                               (r'/(\d+)', SpecificPostHandler),('/.json', JsonMainHandler),
			       (r'/(\d+)'+".json",JsonSpecificPostHandler),('/signup', Signup),
			       ('/login', Login),('/logout', Logout), 
                               ('/flush', FlushHandler), ('/welcome', Welcome)], debug=True)
