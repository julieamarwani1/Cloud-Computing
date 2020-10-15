import os
import sys
from os import environ as env


def create_and_validate_cfg_dict(list_of_nodes):
    """
    :param list_of_nodes: A list of all nodes that should be created on initialization
    :return: a dict with the node-name as key and the config file for said node as valueI
    """
    file_paths_dict = {}
    for node in list_of_nodes:
        file_path = os.getcwd() + f'/configs/{node}-cloud-cfg.yml'
        if os.path.isfile(file_path):
            file_paths_dict[node] = open(file_path)
        else:
            sys.exit(f"{file_path} is not in current working directory")
    return file_paths_dict
            
def get_credentials():
    """
    :return: A dict containing authorization credentials for the keystone loader
    """
    cred = {'auth_url': env['OS_AUTH_URL'],
            'username': env['OS_USERNAME'],
            'password': env['OS_PASSWORD'],
            'project_name': env['OS_PROJECT_NAME'],
            'project_domain_name': env['OS_USER_DOMAIN_NAME'],
            'project_id': env['OS_PROJECT_ID'],
            'user_domain_name': env['OS_USER_DOMAIN_NAME']}
    return cred

