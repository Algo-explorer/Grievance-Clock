"""Never let unit tests initialize the developer's Atlas database."""
import os
os.environ['MONGODB_URI']=''
os.environ['APP_ENV']='development'
os.environ['AUTH_MODE']='local'
