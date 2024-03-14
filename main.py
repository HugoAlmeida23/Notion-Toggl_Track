import PySimpleGUI as sg
import requests
import json
import re
import os
from notion_client import Client
from pprint import pprint
from base64 import b64encode
from datetime import datetime

def main():
    start_date, end_date = get_lastupdate()
    if start_date and end_date:
        sg.popup(f'O ultimo update foi entre {start_date} e {end_date} !', background_color='#3f3f3f', text_color='white')
    else:
        sg.popup('Nenhum update registado!', background_color='#3f3f3f', text_color='white')
    
    sg.theme('DarkGrey4')  # Setting a dark-themed background color
    
    layout = [
        [sg.Text("Base de Dados", text_color='white'), sg.InputText(key='notion_database_id')],
        [sg.Input(key='start_date', size=(20,1)), sg.CalendarButton("Data Inicial", close_when_date_chosen=True,  target='start_date', location=(0,0), no_titlebar=False, button_color=('white', '#404040'))],
        [sg.Input(key='end_date', size=(20,1)), sg.CalendarButton("Data Final", close_when_date_chosen=True,  target='end_date', location=(0,0), no_titlebar=False, button_color=('white', '#404040'))],
        [sg.Multiline(size=(80, 10), key='-DATA-', autoscroll=True, background_color='#3f3f3f', text_color='white')],  # Multiline text element to display data
        [sg.Button('Importar', button_color=('white', '#404040'))]
    ]

    window = sg.Window('Notion-Toggl Track', layout)

    while True:
        event, values = window.read()
        if event == sg.WINDOW_CLOSED:
            break
        elif event == 'Importar':
            notion_database_id = values['notion_database_id']
            notion_database_id = extrair_id(notion_database_id)
            date_object = datetime.strptime(values['start_date'], "%Y-%m-%d %H:%M:%S")
            start_date = date_object.strftime("%Y-%m-%d")
            date_object = datetime.strptime(values['end_date'], "%Y-%m-%d %H:%M:%S")
            end_date = date_object.strftime("%Y-%m-%d")
            valid_email = get_email()
            valid_password = get_password()
            notion_token = get_token()
            workspace_id = get_workspace_id()
            
            client = Client(auth=notion_token)

            summary_data = post_project_summary(valid_email, valid_password, workspace_id, start_date, end_date)
            data = get_user_details(valid_email,valid_password,workspace_id)
            toggl_original_data = togll_run(start_date, end_date, valid_email, valid_password,workspace_id)
            data_processed = process_toggl_data(summary_data,data,toggl_original_data,valid_email,valid_password,workspace_id)
            
            getPageID(client,notion_database_id)
            notion_info_file = "simple_rows.json"
            
            write_from_toggl(data_processed,client,notion_database_id,notion_info_file) 
            write_dates_json(start_date,end_date)
            
            sg.popup('Update successful!', background_color='#3f3f3f', text_color='white')
            window['-DATA-'].update('\n'.join([f"Projeto : {project['project_name']}\nCliente : {project['client_name']}\nResponsável : {project['user_id']}\nTempo Trabalho : {project['seconds']} seconds \n" for project in data_processed]))
            window['Importar'].update(visible=False)

    window.close()
    
def write_dates_json(start_date,end_date):
    info = {
        "start": start_date,
        "end": end_date,
    }
    
    with open('lastupdate.json', 'w') as outfile:
        json.dump(info, outfile)
        
def get_lastupdate():
    if os.path.exists('lastupdate.json'):
        with open('lastupdate.json', 'r') as handler:
            info = json.load(handler)
        
        start_date = info.get('start', None)
        end_date = info.get('end', None)
        
        return start_date, end_date
    else:
        return None, None
    
def extrair_id(notion_database_id):
    padrao = r'\/([^\/\?]+)\?'
    resultado = re.search(padrao, notion_database_id)
    if resultado:
        return resultado.group(1)
    else:
        return None
    
def getPageID(client,notion_databaseid):
    
    db_rows = client.databases.query(database_id=notion_databaseid)
    
    write_dict_to_file_as_json(db_rows, 'db_rows.json')
    
    simple_rows = []
    
    for row in db_rows['results']:
        client_name = safe_get(row, 'properties.Cliente.title.0.text.content')
        project = safe_get(row, 'properties.Projeto.rich_text.0.text.content')
        user_id = safe_get(row, 'properties.Funcionario.rich_text.0.text.content')
        hours = safe_get(row, 'properties.Tempo.number')
        url = safe_get(row, 'url')
        
        match = re.search(r'(?<=-)[a-f0-9]{32}', url)

        if match:
            id_from_url = match.group(0)
            print("ID extraído da URL:", id_from_url)
        else:
            print("ID não encontrado na URL")
            
        simple_rows.append({
            'client': client_name,
            'projeto': project,
            'horas': hours,
            'user_id': user_id,
            'url': id_from_url
        })
    
    write_dict_to_file_as_json(simple_rows,'simple_rows.json')
    
def process_toggl_data(toggl_data,data,toggl_original_data,valid_email,valid_password,workspace_id):
    
    toggl_data = make_secondsright(toggl_data)
    if toggl_data is not None:
        processed_toggl_data = []
        
        for project in toggl_data:
            project_id = project.get("project_id")
            #ja temos a data dos user ids, vmaos comparar o user id dessa data com o user id daqui, e pegar no nome dele
            user_id = project.get("user_id")
            if project_id is not None:
                project_name = get_project_name(valid_email,valid_password,workspace_id,project_id)
                user_name = get_user_name(user_id,data)
                client_name = get_client_name(project_name,toggl_original_data)
                if project_name is not None:
                    if project_name is not None:
                        project_name = project_name.get("name")
                        user_id = user_name
                        seconds = project.get("seconds")
                    
                    # Adiciona os dados processados à lista
                    processed_toggl_data.append({
                        "project_name": project_name,
                        "client_name": client_name,
                        "user_id": user_id,
                        "seconds": seconds
                    }) 
                    
                else:
                    print("Failed to fetch client details for project:", project.get("project_id"))
            else:
                print("Project ID not found for project:", project.get("project_id"))
            
    else:
        print("toggl_data is None")
                    
    return processed_toggl_data
    
def togll_run(start_date, end_date, valid_email, valid_password,workspace_id):
    # Chama a função toggl_search para obter os dados dos projetos do usuário
    toggl_data = toggl_search(start_date, end_date, valid_email, valid_password)
    print("Dados do toggl", toggl_data)
    # Verifica se os dados foram obtidos com sucesso
    if toggl_data is not None:
        # Lista para armazenar os dados dos projetos com os detalhes do cliente e os segundos reais
        processed_projects = []
        
        # Itera sobre os projetos e obtém os detalhes do cliente para cada projeto
        for project in toggl_data:
            print("Toggl data 123", toggl_data)
            client_id = project.get("client_id")
            print("Client ID", client_id)
            if client_id is not None:
                client_details = get_client_details(valid_email, valid_password, workspace_id, client_id)
                if client_details is not None:
                    # Salva o nome do projeto, o nome do cliente e os segundos reais em variáveis
                    project_name = project.get("name")
                    client_name = client_details.get("name")
                    actual_seconds = project.get("actual_seconds")
                    
                    # Adiciona os dados processados à lista
                    processed_projects.append({
                        "project_name": project_name,
                        "client_name": client_name,
                        "actual_seconds": actual_seconds
                    })
                
                    
                else:
                    print("Failed to fetch client details for project:", project.get("name"))
            else:
                print("Client ID not found for project:", project.get("name"))
        
        # Exibe os dados processados
        print("Processed Projects:", processed_projects)
        
    else:
        print("Failed to fetch user projects data. Exiting...")
        
    return processed_projects

def get_client_details(email, password, workspace_id, client_id):
    # Codifica as credenciais de autenticação para serem enviadas no cabeçalho Authorization
    auth_string = "{}:{}".format(email, password)
    auth_header = "Basic {}".format(b64encode(auth_string.encode()).decode("ascii"))
    
    # Faz a solicitação GET para a API do Toggl para obter os detalhes do cliente pelo ID
    url = f'https://api.track.toggl.com/api/v9/workspaces/{workspace_id}/clients/{client_id}'
    response = requests.get(url, headers={'content-type': 'application/json', 'Authorization': auth_header})
    
    # Verifica se a solicitação foi bem sucedida e retorna os dados em formato JSON
    if response.status_code == 200:  
        return response.json()
    else:
        print("Failed to fetch client details:", response.status_code)
        return None
    
def get_project_name(email, password, workspace_id,project_id):
    # Codifica as credenciais de autenticação para serem enviadas no cabeçalho Authorization
    auth_string = "{}:{}".format(email, password)
    auth_header = "Basic {}".format(b64encode(auth_string.encode()).decode("ascii"))
    
    # Faz a solicitação GET para a API do Toggl para obter os detalhes do cliente pelo ID
    url = f'https://api.track.toggl.com/api/v9/workspaces/{workspace_id}/projects/{project_id}'
    response = requests.get(url, headers={'content-type': 'application/json', 'Authorization': auth_header})
    
    # Verifica se a solicitação foi bem sucedida e retorna os dados em formato JSON
    if response.status_code == 200:  
        return response.json()
    else:
        print("Failed to fetch client details:", response.status_code)
        return None

def get_user_details(email, password, workspace_id):
    # Codifica as credenciais de autenticação para serem enviadas no cabeçalho Authorization
    auth_string = "{}:{}".format(email, password)
    auth_header = "Basic {}".format(b64encode(auth_string.encode()).decode("ascii"))
    
    # Faz a solicitação GET para a API do Toggl para obter os detalhes do cliente pelo ID
    url = f'https://api.track.toggl.com/api/v9/workspaces/{workspace_id}/users'
    response = requests.get(url, headers={'content-type': 'application/json', 'Authorization': auth_header})
    
    # Verifica se a solicitação foi bem sucedida e retorna os dados em formato JSON
    if response.status_code == 200:  
        return response.json()
    else:
        print("Failed to fetch client details:", response.status_code)
        return None
    
def get_user_name(user_id,data):
    for user in data:
        if user.get("id") == user_id:
            return user.get("fullname")
        
def make_secondsright(toggl_data):
    for item in toggl_data:
        seconds = item['seconds']
        total_seconds = sum(seconds)
        item['seconds'] = total_seconds
        
    return toggl_data

def get_client_name(project_name,toggl_original_data):
    for item in toggl_original_data:
        if item.get("project_name") == project_name.get("name"):
            return item.get("client_name")
        
def toggl_search(start_date, end_date, email, password):
    
    def get_user_projects(email, password):
        # Codifica as credenciais de autenticação para serem enviadas no cabeçalho Authorization
        auth_string = "{}:{}".format(email, password)
        auth_header = "Basic {}".format(b64encode(auth_string.encode()).decode("ascii"))
        
        # Faz a solicitação GET para a API do Toggl para obter os projetos do usuário
        response = requests.get('https://api.track.toggl.com/api/v9/me/projects', 
                                headers={'Content-Type': 'application/json', 'Authorization': auth_header})
        
        # Verifica se a solicitação foi bem sucedida e retorna os dados em formato JSON
        if response.status_code == 200:
            projects = response.json()
            print(projects)
            # Extracting only desired variables from each project
            extracted_projects = []
            for project in projects:
                extracted_project = {
                    "name": project["name"],
                    "client_id": project["client_id"],
                    "actual_seconds": project["actual_seconds"]
                }
                extracted_projects.append(extracted_project)
            
            return extracted_projects
        else:
            print("Failed to fetch projects:", response.status_code)
            return None

    # Obtém os projetos do usuário e imprime os resultados
    projects = get_user_projects(email, password)
    if projects is not None:
        print("User Projects:", projects)
        
    return projects

def write_text(client, page_id, text, type):
    client.blocks.children.append(
        block_id=page_id,
        children=[
            {
                "object": "block",
                "type": type,
                type: {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": text
                            }
                        }
                    ]
                }
            }
        ]
    )
    
def write_dict_to_file_as_json(content, file_name):
    content_as_json_str = json.dumps(content)

    with open(file_name, 'w') as f:
        f.write(content_as_json_str)
        
def read_text(client, page_id):
    response = client.blocks.children.list(block_id=page_id)
    return response['results']

def create_simple_blocks_from_content(client, content):
    
    page_simple_blocks = []

    for block in content:

        block_id = block['id']
        block_type = block['type']
        has_children = block['has_children']
        rich_text = block[block_type].get('rich_text')

        if not rich_text:
            continue


        simple_block = {
            'id': block_id,
            'type': block_type,
            'text': rich_text[0]['plain_text']
        }

        if has_children:
            nested_children = read_text(client, block_id)
            simple_block['children'] = create_simple_blocks_from_content(client, nested_children)

        page_simple_blocks.append(simple_block)


    return page_simple_blocks

def safe_get(data, dot_chained_keys):
    keys = dot_chained_keys.split('.')
    for key in keys:
        try:
            if isinstance(data, list):
                if key.isdigit():  # Check if the key is an integer
                    data = data[int(key)]
                else:
                    return None  # Key is not an integer, cannot access list element
            else:
                data = data[key]
        except (KeyError, TypeError, IndexError):
            return None
    return data

def write_row(client, database_id, client_name, hours, project_name):

    client.pages.create(
        **{
            "parent": {
                "database_id": database_id
            },
            'properties': {
                'Cliente': {'title': [{'text': {'content': client_name}}]},
                'Projeto': {'rich_text': [{'text': {'content': project_name}}]},
                'Tempo': {'number': hours},   
            }
        }
    )
    
def write_1row(client,notion_database_id,client_name,hours,project_name,url):


    page_id = url #preciso de fazer a comapraçao dos projetos e encontrar o url

    # Define the properties you want to update
    properties = {
        #'Cliente': {'title': [{'text': {'content': client_name}}]},
        #'Projeto': {'rich_text': [{'text': {'content': project_name}}]},
        'Tempo': {'number': hours},  # Note: 'number' value should be an integer, not a string
    }

    # Update the page
    client.pages.update(page_id=page_id, properties=properties)
    # IT WORKSSSSS LETS FUCKING GO
       
def tests(): 
    
    '''client = Client(auth=notion_token)
     
    content = read_text(client, notion_database_id)
    
    write_dict_to_file_as_json(content, 'content.json')

    simple_blocks = create_simple_blocks_from_content(client, content)

    write_dict_to_file_as_json(simple_blocks, 'simple_blocks.json')
    
    db_info = client.databases.retrieve(database_id=notion_database_id)
    
    write_dict_to_file_as_json(db_info,'db_info.json')
    
    db_rows = client.databases.query(database_id=notion_database_id)
    
    write_dict_to_file_as_json(db_rows, 'db_rows.json')
    
    simple_rows = []
    
    for row in db_rows['results']:
        client_name = safe_get(row, 'properties.Cliente.title.0.text.content')
        project = safe_get(row, 'properties.Projeto.rich_text.0.text.content')
        hours = safe_get(row, 'properties.Tempo.number')
        
        simple_rows.append({
            'client': client_name,
            'projeto': project,
            'horas': hours
        })
    
    write_dict_to_file_as_json(simple_rows,'simple_rows.json')'''
          
def write_from_toggl(objetsToggl,client,notion_database_id,notion_info_file):

    #abre o ficheiro simple_rows
    with open(notion_info_file, "r") as file:
        notion_info = json.load(file)
    
    
    for project in objetsToggl:
        client_name = project.get("client_name")
        project_name = project.get("project_name")
        user_id = project.get("user_id")
        hours = project.get("seconds")
        
        # Obter o URL correspondente do notioninfo
        url = get_url_from_notioninfo(project_name, user_id, notion_info)
        horas = get_hours_from_notion(project_name, user_id, notion_info)
        
        if horas is not None:
            total = horas + hours
        if hours is None:
            total = hours
            
        if url:
            write_1row(client, notion_database_id, client_name, total, project_name, url)
        else:
            print(f"Projeto '{project_name}' não encontrado no arquivo notioninfo")
          
def get_url_from_notioninfo(project_name,user_id, notion_info):
    
    for item in notion_info:
        if item["projeto"] == project_name and item["user_id"] == user_id:
            return item["url"]
    return None  # Retorna None se o projeto não for encontrado

def get_hours_from_notion(project_name,user_id, notion_info):
    
    for item in notion_info:
        if item["projeto"] == project_name and item["user_id"] == user_id:
            return item["horas"]
    return None  # Retorna None se o projeto não for encontrado

def seconds_to_minutes(seconds):
    # Calcula o número de minutos
    minutes = seconds // 60
    
    # Calcula o número de segundos restantes
    remaining_seconds = seconds % 60
    
    # Retorna uma string formatada com minutos e segundos
    return f"{minutes}m{remaining_seconds}s"

def post_project_summary(email, password, workspace_id, start_date, end_date):
    # Codifica as credenciais de autenticação para serem enviadas no cabeçalho Authorization
    auth_string = "{}:{}".format(email, password)
    auth_header = "Basic {}".format(b64encode(auth_string.encode()).decode("ascii"))

    # Define os dados a serem enviados no corpo da solicitação
    payload = {
        "start_date": start_date,
        "end_date": end_date
    }

    # Faz a solicitação POST para o endpoint fornecido
    response = requests.post(
        f'https://api.track.toggl.com/reports/api/v3/workspace/{workspace_id}/weekly/time_entries',
        json=payload,
        headers={'content-type': 'application/json', 'Authorization': auth_header}
    )

    # Verifica se a solicitação foi bem-sucedida e retorna os dados em formato JSON
    if response.status_code == 200:
        return response.json()
    else:
        print("Failed to fetch project summary:", response.status_code)
        return None

def test_json():
    with open('credentials.json', 'r') as handler:
        info = json.load(handler)

    users = info['user']
    passwords = info['password']
    token = info['token']
    workspace_id = info['workspace']
    
    print("User: '{}' Password: '{}' Token: '{}' WorkspaceID: '{}'".format(users[0], passwords[0], token[0], workspace_id[0]))
    
    #data = create_json(users, passwords, token, workspace_id)
    #print(data)
    
    return users[0], passwords[0]

def get_email():
    with open('info.json', 'r') as handler:
        info = json.load(handler)
        
    email = info['email']
    
    return email

def get_password():
    
    with open('info.json', 'r') as handler:
        info = json.load(handler)
        
    passwords = info['password']
    
    return passwords

def get_token():
    
    with open('info.json', 'r') as handler:
        info = json.load(handler)
        
    token = info['token']
    
    return token

def get_workspace_id():
    
    with open('info.json', 'r') as handler:
        info = json.load(handler)
        
    workspace_id = info['workspace']
    
    return workspace_id
    
def create_json(user,password,token,workspace_id):
    passwords = []
    
    passwords.append({
            'user': user,
            'password': password,
            'token': token,
            'workspace': workspace_id
        })
    
    content_as_json_str = json.dumps(passwords)

    with open('passwords.json', 'w') as f:
        f.write(content_as_json_str)
        
    with open('passwords.json', "r") as file:
        notion_info = json.load(file)
        
    for item in notion_info:
            return item["user"]
    
if __name__ == '__main__':
    main()
    
    