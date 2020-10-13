
from keystoneauth1 import loading
from keystoneauth1 import session
from heatclient import client
from util import get_credentials
import os
import yaml 

def create(stack_name= 'max1'):
    loader = loading.get_plugin_loader('password')

    credentials = get_credentials()
    auth = loader.load_from_options(**credentials)

    sess = session.Session(auth=auth)
    heat = client.Client('1', session=sess)
    for stack in heat.stacks.list():
        if 'max1' in stack.name.lower():
            print('stack already exists')
            return False



    file_path = os.getcwd() + f'/heat.yml'
    if os.path.isfile(file_path):
        args = yaml.safe_load(open(file_path))
        args['heat_template_version'] = '2013-05-23'
    else:
        print(f"{file_path} is not in current working directory")
        return False

    #print(args)
    heat.stacks.create(stack_name='max1', template=args)
    return True
