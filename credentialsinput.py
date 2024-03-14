import PySimpleGUI as sg
import requests
import json
import re
from notion_client import Client
from pprint import pprint
from base64 import b64encode

def main():
    layout = [
        [sg.Text("Email"), sg.InputText(key='email',)],
        [sg.Text("Password"), sg.InputText(key='password')],
        [sg.Text("Notion Token"), sg.InputText(key='notion_token')],
        [sg.Text('Workspace ID'), sg.InputText(key='workspace_id')],
        [sg.Button('Inserir')]
    ]

    window = sg.Window('Data Input', layout)

    while True:
        event, values = window.read()
        if event == sg.WINDOW_CLOSED:
            break
        elif event == 'Inserir':
            
            email = values['email']
            password = values['password']
            notion_token = values['notion_token']
            workspace_id = values['workspace_id']
            
            write_json(email, password, notion_token, workspace_id)
            data = get_email()
            print(data)
            break
        
    window.close()
    
def write_json(email, password, notion_token, workspace_id):
    info = {
        "email": email,
        "password": password,
        "token": notion_token,
        "workspace": workspace_id
    }
    
    with open('info.json', 'w') as outfile:
        json.dump(info, outfile)
        
def get_email():
    
    with open('info.json', 'r') as handler:
        info = json.load(handler)
        
    users = info['email']
    
    return users[0]

        
if __name__ == '__main__':
    main()
    