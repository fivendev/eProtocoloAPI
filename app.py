from flask import Flask, request, jsonify
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import requests
import json
import random
from datetime import datetime

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Cria a pasta se não existir


@app.route('/email', methods=['POST'])
def send_email():
    db_url = "https://eprotoccolo-default-rtdb.firebaseio.com/"

    # Obter dados do formulário
    user_id = request.form.get("user_id")
    titulo_protocolo = request.form.get("titulo")
    destinatario = request.form.get("destinatario")
    destinatario_nome = request.form.get("destinatario_nome")
    remetente_nome = request.form.get("remetente_nome")
    arquivos = request.files.getlist("imagens")

    # Validação de campos obrigatórios
    if not all([destinatario, user_id, titulo_protocolo, remetente_nome]):
        return jsonify({"erro": "Campos obrigatórios faltando"}), 400

    try:
        # Gerar ID único para o protocolo
        protocol_id = requests.post(f'{db_url}/protocolos/{user_id}/.json',
                                    json={}).json()['name']

        # Salvar metadados do protocolo
        protocol_data = {
            "titulo": titulo_protocolo,
            "destinatario_nome": destinatario_nome,
            "destinatario_email": destinatario,
            "data": datetime.now().strftime("%d/%m/%Y"),
            "hora": datetime.now().strftime("%H:%M:%S"),
            "documentos_qtd": len(arquivos),
            "status": "pendente",
            "stt": "pendente",
            "user_id": user_id,
            "protocol_id": protocol_id
        }

        requests.patch(f'{db_url}/protocolos/{user_id}/{protocol_id}.json',
                       json=protocol_data)

        # Configurações do e-mail
        sysemail = "eprotocolosystem@zohomail.com"
        syssenha = "264079PizzaHot"
        assunto = f"eProtocolo recebido de {remetente_nome}: {titulo_protocolo}"

        # Criar e-mail HTML estilizado
        corpo_email_html = f"""
        <html>
        <body>
            <h3>{remetente_nome} enviou um novo protocolo</h3>
            <p>Título: {titulo_protocolo}</p>

            <div style="margin: 20px 0;">
                <a href="https://37b51707-453d-4f2b-b0c2-3d061ee2daf1-00-3uyykj8p6ey3q.kirk.replit.dev/confirmar-protocolo/{user_id}/{protocol_id}?email={destinatario}"
                   style="background: #27ae60; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; margin-right: 10px;">
                   ✅ Confirmar Recebimento
                </a>

                <a href="https://37b51707-453d-4f2b-b0c2-3d061ee2daf1-00-3uyykj8p6ey3q.kirk.replit.dev/rejeitar-protocolo/{user_id}/{protocol_id}?email={destinatario}"
                   style="background: #e74c3c; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px;">
                   ❌ Rejeitar Protocolo
                </a>
            </div>
        </body>
        </html>
        """

        # Configurar mensagem
        msg = MIMEMultipart()
        msg['From'] = sysemail
        msg['To'] = destinatario
        msg['Subject'] = assunto
        msg.attach(MIMEText(corpo_email_html, 'html'))

        # Anexar arquivos
        for arquivo in arquivos:
            caminho = os.path.join(UPLOAD_FOLDER, arquivo.filename)
            arquivo.save(caminho)

            with open(caminho, "rb") as f:
                anexo = MIMEBase("application", "octet-stream")
                anexo.set_payload(f.read())
                encoders.encode_base64(anexo)
                anexo.add_header("Content-Disposition",
                                 f"attachment; filename={arquivo.filename}")
                msg.attach(anexo)

        # Enviar e-mail
        server = smtplib.SMTP_SSL('smtp.zoho.com', 465)
        server.login(sysemail, syssenha)
        server.sendmail(sysemail, destinatario, msg.as_string())

        return jsonify({
            "mensagem": "Protocolo enviado com sucesso!",
            "protocol_id": protocol_id,
            "detalhes": protocol_data
        })

    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        server.quit()
        # Limpar arquivos temporários
        for arquivo in arquivos:
            caminho = os.path.join(UPLOAD_FOLDER, arquivo.filename)
            if os.path.exists(caminho):
                os.remove(caminho)


@app.route('/confirmar-protocolo/<user_id>/<protocol_id>', methods=['GET'])
def confirmar_protocolo(user_id, protocol_id):
    db_url = "https://eprotoccolo-default-rtdb.firebaseio.com/"
    try:
        email_param = request.args.get('email')

        # Buscar dados do protocolo
        response = requests.get(
            f'{db_url}/protocolos/{user_id}/{protocol_id}/.json')

        if response.status_code != 200:
            return "<h2>Erro: Protocolo não encontrado</h2>", 404

        protocolo = response.json()

        # Validações
        if protocolo.get('destinatario_email') != email_param:
            return "<h2>Ação não autorizada</h2>", 403

        if protocolo.get('status') != 'pendente':
            return "<h2>Protocolo já processado</h2>", 400

        # Atualizar status
        updates = {
            "status": "recebido",
            "data_confirmacao": datetime.now().isoformat()
        }

        requests.patch(f'{db_url}/protocolos/{user_id}/{protocol_id}/.json',
                       json=updates)

        return """
        <html>
        <body style="text-align: center; padding: 50px;">
            <h2 style="color: #27ae60;">✅ Protocolo Confirmado!</h2>
            <p>O recebimento foi registrado com sucesso.</p>
            <p>Esta janela pode ser fechada.</p>
        </body>
        </html>
        """

    except Exception as e:
        return f"<h2>Erro: {str(e)}</h2>", 500


@app.route('/rejeitar-protocolo/<user_id>/<protocol_id>', methods=['GET'])
def rejeitar_protocolo(user_id, protocol_id):
    db_url = "https://eprotoccolo-default-rtdb.firebaseio.com/"
    try:
        email_param = request.args.get('email')

        response = requests.get(
            f'{db_url}/protocolos/{user_id}/{protocol_id}/.json')

        if response.status_code != 200:
            return "<h2>Erro: Protocolo não encontrado</h2>", 404

        protocolo = response.json()

        if protocolo.get('destinatario_email') != email_param:
            return "<h2>Ação não autorizada</h2>", 403

        if protocolo.get('status') != 'pendente':
            return "<h2>Protocolo já processado</h2>", 400

        updates = {
            "status": "rejeitado",
            "data_rejeicao": datetime.now().isoformat()
        }

        requests.patch(f'{db_url}/protocolos/{user_id}/{protocol_id}/.json',
                       json=updates)

        return """
        <html>
        <body style="text-align: center; padding: 50px;">
            <h2 style="color: #e74c3c;">❌ Protocolo Rejeitado!</h2>
            <p>A rejeição foi registrada com sucesso.</p>
            <p>Esta janela pode ser fechada.</p>
        </body>
        </html>
        """

    except Exception as e:
        return f"<h2>Erro: {str(e)}</h2>", 500


@app.route('/register', methods=['POST'])
def register():
    url = 'https://eprotoccolo-default-rtdb.firebaseio.com'

    email = request.json.get('email')
    senha = request.json.get('password')
    nome = request.json.get('nome')
    sobrenome = request.json.get('sobrenome')

    # Verificar se o email já está cadastrado
    req_user = requests.get(f'{url}/users.json')

    if req_user.status_code == 200:
        print('Conectado')
        users = json.loads(
            req_user.text)  # Converte a resposta JSON em um objeto Python

        if isinstance(users, list):  # Verifica se é uma lista
            for user in users:
                if isinstance(user, dict) and 'email' in user:
                    if email == user['email']:  # Comparação correta
                        print('Email já cadastrado')
                        return "email já cadastrado"

        # Se não achou o e-mail nos usuários cadastrados, verifica o pré-registro
        req_pre_user = requests.get(f'{url}/pre_register.json')

        if req_pre_user.status_code == 200:
            prusers = json.loads(req_pre_user.text)  # Pode ser um dicionário

            if prusers is not None:  # Evita erro se a resposta for vazia
                if isinstance(prusers, dict):  # Firebase retorna dicionário
                    for pruser in prusers.values():
                        if isinstance(pruser, dict) and 'email' in pruser:
                            if email == pruser['email']:
                                print('Esse email já está em pré-registro!')
                                return 'pre-registro'

        # Caso o usuário não esteja cadastrado ou em pré-registro, criar um código de confirmação
        code = random.randint(100000, 999999)

        # Adicionar usuário ao pré-registro
        data = {
            "email": email,
            "senha": senha,
            "nome": nome,
            "sobrenome": sobrenome,
            "confirm_code": code
        }

        requests.post(f'{url}/pre_register.json', json=data)
        print("Usuário adicionado ao pré-registro com código:", code)

        sysemail = "eprotocolosystem@zohomail.com"
        syssenha = "264079PizzaHot"
        assunto = f"Seu código de confrimação de cadastro é: {code}"

        # Criar email HTML
        corpo_email_html = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: 'Arial', sans-serif;
                background-color: #f4f4f4;
                text-align: center;
                padding: 20px;
            }}
            .container {{
                background-color: #ffffff;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0px 0px 10px rgba(0, 0, 0, 0.1);
                display: inline-block;
                width: 100%;
                max-width: 450px;
            }}
            .header {{
                font-size: 22px;
                font-weight: bold;
                color: #1E3A8A; /* Azul escuro */
                margin-bottom: 15px;
            }}
            .code {{
                font-size: 28px;
                font-weight: bold;
                color: #007BFF; /* Azul */
                padding: 12px;
                border: 2px dashed #007BFF; /* Borda azul */
                display: inline-block;
                margin-top: 10px;
                letter-spacing: 2px;
            }}
            p {{
                color: #555;
                font-size: 16px;
            }}
            .footer {{
                margin-top: 20px;
                font-size: 14px;
                color: #777;
                border-top: 1px solid #ddd;
                padding-top: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">eProtocolo</div>
            <p>Olá,</p>
            <p>Olá {nome}, seu código de confirmação para ativação do cadastro no eProtocolo é:</p>
            <div class="code">{code}</div>
            <p>Se você não solicitou este código, ignore este e-mail.</p>
            <div class="footer">
                Tecnologia eProtocolo<br>
                Desenvolvido por Lucas Lima
            </div>
        </div>
    </body>
    </html>
    """

        # Criar e-mail
        msg = MIMEMultipart()
        msg['From'] = sysemail
        msg['To'] = email
        msg['Subject'] = assunto
        msg.attach(MIMEText(corpo_email_html, 'html'))

        # Salvar e anexar imagens
        arquivos = request.files.getlist("imagens")
        for arquivo in arquivos:
            caminho = os.path.join(UPLOAD_FOLDER, arquivo.filename)
            arquivo.save(caminho)

            with open(caminho, "rb") as f:
                anexo = MIMEBase("application", "octet-stream")
                anexo.set_payload(f.read())
                encoders.encode_base64(anexo)
                anexo.add_header("Content-Disposition",
                                 f"attachment; filename={arquivo.filename}")
                msg.attach(anexo)

        # Enviar e-mail
        try:
            server = smtplib.SMTP_SSL('smtp.zoho.com', 465)
            server.login(sysemail, syssenha)
            server.sendmail(sysemail, email, msg.as_string())
            print('email enviado')
        except Exception as e:
            return print(({"erro": str(e)}), 500)
        finally:
            server.quit()

        return "Usuário adicionado ao pré-registro"

    return 'Erro ao conectar'


@app.route('/confirm', methods=['POST'])
def confirm_account():
    url = 'https://eprotoccolo-default-rtdb.firebaseio.com/'
    email = request.json.get('email')
    code = request.json.get('code')

    req = requests.get(f'{url}/pre_register.json')
    if req.status_code == 200:
        users = req.json()  # Já converte direto para um dicionário

        if users:
            for user_id, user in users.items(
            ):  # Obtém chave e valores do usuário
                if email == user.get('email'):
                    confirm_code = user.get('confirm_code')
                    if code == confirm_code:
                        nome = user.get('nome')
                        sobrenome = user.get('sobrenome')
                        senha = user.get('senha')

                        userdata = {
                            "nome": nome,
                            "sobrenome": sobrenome,
                            "email": email,
                            "senha": senha
                        }

                        req_user = requests.post(f'{url}/users.json',
                                                 json=userdata)
                        if req_user.status_code == 200:
                            print(user)

                            # Agora deletamos corretamente com a chave do usuário
                            req_del = requests.delete(
                                f'{url}/pre_register/{user_id}.json')
                            if req_del.status_code == 200:
                                sysemail = "eprotocolosystem@zohomail.com"
                                syssenha = "264079PizzaHot"
                                assunto = "Bem-vindo ao eProtocolo!"

                                # Criar email HTML
                                corpo_email_html = f"""
                                <html>
                                <head>
                                    <style>
                                        body {{
                                            font-family: 'Arial', sans-serif;
                                            background-color: #f4f4f4;
                                            text-align: center;
                                            padding: 20px;
                                        }}
                                        .container {{
                                            background-color: #ffffff;
                                            padding: 20px;
                                            border-radius: 10px;
                                            box-shadow: 0px 0px 10px rgba(0, 0, 0, 0.1);
                                            display: inline-block;
                                            width: 100%;
                                            max-width: 450px;
                                        }}
                                        .header {{
                                            font-size: 22px;
                                            font-weight: bold;
                                            color: #1E3A8A; /* Azul escuro */
                                            margin-bottom: 15px;
                                        }}
                                        p {{
                                            color: #555;
                                            font-size: 16px;
                                            text-align: left;
                                        }}
                                        .footer {{
                                            margin-top: 20px;
                                            font-size: 14px;
                                            color: #777;
                                            border-top: 1px solid #ddd;
                                            padding-top: 10px;
                                        }}
                                    </style>
                                </head>
                                <body>
                                    <div class="container">
                                        <div class="header">Bem-vindo ao eProtocolo!</div>
                                        <p>Olá {nome},</p>
                                        <p>É um prazer tê-lo(a) conosco! O eProtocolo foi desenvolvido para oferecer mais praticidade, segurança e eficiência na gestão de processos e documentos.</p>
                                        <p>A partir de agora, você terá acesso a uma plataforma moderna e intuitiva para organizar suas demandas com mais agilidade.</p>
                                        <p>Se precisar de qualquer ajuda, nossa equipe está à disposição para te auxiliar.</p>
                                        <p>Seja bem-vindo(a) e aproveite ao máximo os recursos que preparamos para você!</p>
                                        <div class="footer">
                                            Tecnologia eProtocolo<br>
                                            Desenvolvido por Lucas Lima
                                        </div>
                                    </div>
                                </body>
                                </html>
                                """

                                # Criar e-mail
                                msg = MIMEMultipart()
                                msg['From'] = sysemail
                                msg['To'] = email
                                msg['Subject'] = assunto
                                msg.attach(MIMEText(corpo_email_html, 'html'))

                                # Salvar e anexar imagens
                                arquivos = request.files.getlist("imagens")
                                for arquivo in arquivos:
                                    caminho = os.path.join(
                                        UPLOAD_FOLDER, arquivo.filename)
                                    arquivo.save(caminho)

                                    with open(caminho, "rb") as f:
                                        anexo = MIMEBase(
                                            "application", "octet-stream")
                                        anexo.set_payload(f.read())
                                        encoders.encode_base64(anexo)
                                        anexo.add_header(
                                            "Content-Disposition",
                                            f"attachment; filename={arquivo.filename}"
                                        )
                                        msg.attach(anexo)

                                # Enviar e-mail
                                try:
                                    server = smtplib.SMTP_SSL(
                                        'smtp.zoho.com', 465)
                                    server.login(sysemail, syssenha)
                                    server.sendmail(sysemail, email,
                                                    msg.as_string())
                                    print('email enviado')
                                except Exception as e:
                                    return print(({"erro": str(e)}), 500)
                                finally:
                                    server.quit()
                                print('Usuário removido do pré-registro')
                                return 'Cadastro Confirmado com Sucesso!'

                            return 'Falha ao remover usuário do pré-registro'

                        return 'Falha ao confirmar cadastro'
                    return 'Código Incorreto'
            return 'Email incorreto'
    return "Erro"


@app.route('/login', methods=['POST'])
def login():
    url = 'https://eprotoccolo-default-rtdb.firebaseio.com'

    email = request.json.get('email')
    senha = request.json.get('password')

    req_user = requests.get(f'{url}/users.json')

    if req_user.status_code == 200:
        users = json.loads(req_user.text)
        print('step 1')

        if isinstance(users, dict):  # Verifica se users é um dicionário
            print('step 2')
            for user_id, user_data in users.items(
            ):  # Itera sobre os pares chave-valor
                if isinstance(
                        user_data, dict
                ) and 'email' in user_data:  # Verifica se user_data é um dicionário e contém a chave 'email'
                    if email == user_data['email'] and senha == user_data[
                            'senha']:
                        print('Login efetuado com sucesso')
                        return {
                            "status_code": 200,
                            "user_data": {
                                "user_id": user_id,
                                "email": email,
                                "nome": user_data['nome'],
                                "sobrenome": user_data['sobrenome'],
                                "img": user_data['img'],
                                "senha": user_data['senha']
                            }
                        }

    return 'incorreto'


@app.route('/getprotocols', methods=['POST'])
def get_protocols():
    db_url = "https://eprotoccolo-default-rtdb.firebaseio.com/protocolos"
    user_id = request.json.get('user_id')

    req = requests.get(f'{db_url}/{user_id}.json')
    data = req.json()

    # Corrigir para retornar um dicionário vazio se não houver dados
    if data is None:
        data = {}  # Alterado de lista para dicionário

    return jsonify(data)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4000, debug=True)
