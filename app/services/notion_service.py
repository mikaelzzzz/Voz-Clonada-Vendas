import logging
import requests
from app.config.settings import Settings

logger = logging.getLogger(__name__)

class NotionService:
    def __init__(self):
        settings = Settings()
        self.api_key = settings.NOTION_API_KEY
        self.database_id = settings.NOTION_DATABASE_ID
        self.api_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

    def _find_page_by_phone(self, phone: str) -> str or None:
        """Busca uma página no Notion pelo número de telefone."""
        try:
            url = f"{self.api_url}/databases/{self.database_id}/query"
            query = {"filter": {"property": "Telefone", "rich_text": {"equals": phone}}}
            response = requests.post(url, headers=self.headers, json=query)
            response.raise_for_status()
            data = response.json()
            if data["results"]:
                return data["results"][0]["id"]
            return None
        except Exception as e:
            error_message = f"Erro ao buscar página no Notion por telefone {phone}: {e}"
            logger.error(error_message)
            print(f"[NOTION_SERVICE_ERROR] {error_message}") # Print para depuração
            return None

    def _parse_properties(self, notion_props: dict) -> dict:
        """Converte as propriedades do Notion para um dicionário simples."""
        data = {}
        for name, prop in notion_props.items():
            prop_type = prop['type']
            if prop_type == 'title' and prop['title']:
                data[name] = prop['title'][0]['text']['content']
            elif prop_type == 'rich_text' and prop['rich_text']:
                data[name] = prop['rich_text'][0]['text']['content']
            elif prop_type == 'email' and prop['email']:
                data[name] = prop['email']
            # Adicione outros tipos se necessário
        return data

    def get_lead_data_by_phone(self, phone: str) -> dict or None:
        """Busca os dados de um lead pelo telefone e retorna um dicionário."""
        page_id = self._find_page_by_phone(phone)
        if not page_id:
            return None
        
        try:
            url = f"{self.api_url}/pages/{page_id}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            page_data = response.json()
            return self._parse_properties(page_data.get("properties", {}))
        except Exception as e:
            error_message = f"Erro ao buscar dados do lead {phone} no Notion: {e}"
            logger.error(error_message)
            print(f"[NOTION_SERVICE_ERROR] {error_message}")
            return None

    def create_or_update_lead(self, sender_name: str, phone: str, photo_url: str = None):
        """
        Cria uma nova página no Notion para um lead se não existir,
        ou atualiza a capa se já existir.
        """
        if not self.api_key or not self.database_id:
            logger.warning("Credenciais do Notion não configuradas. Serviço desabilitado.")
            return

        page_id = self._find_page_by_phone(phone)

        properties = {
            "Cliente": {"title": [{"text": {"content": sender_name}}]},
            "Telefone": {"rich_text": [{"text": {"content": phone}}]},
            "Link Rápido WhatsApp": {"url": f"https://wa.me/{phone}"}
        }

        if page_id:
            logger.info(f"Lead com telefone {phone} já existe (Page ID: {page_id}). Atualizando...")
            update_url = f"{self.api_url}/pages/{page_id}"
            payload = {"properties": properties}
            if photo_url:
                payload["cover"] = {"type": "external", "external": {"url": photo_url}}

            try:
                response = requests.patch(update_url, headers=self.headers, json=payload)
                response.raise_for_status()
                logger.info(f"Página do lead {phone} atualizada com sucesso.")
            except Exception as e:
                error_message = f"Erro ao atualizar página no Notion para o lead {phone}: {e}"
                logger.error(error_message)
                print(f"[NOTION_SERVICE_ERROR] {error_message}") # Print para depuração
        else:
            logger.info(f"Criando novo lead no Notion para {phone}...")
            create_url = f"{self.api_url}/pages"
            payload = {
                "parent": {"database_id": self.database_id},
                "properties": properties,
            }
            if photo_url:
                payload["cover"] = {"type": "external", "external": {"url": photo_url}}

            try:
                response = requests.post(create_url, headers=self.headers, json=payload)
                response.raise_for_status()
                logger.info(f"Novo lead {phone} criado no Notion com sucesso.")
            except Exception as e:
                error_message = f"Erro ao criar página no Notion para o lead {phone}: {e}"
                logger.error(error_message)
                print(f"[NOTION_SERVICE_ERROR] {error_message}") # Print para depuração

    def update_lead_properties(self, phone: str, updates: dict):
        """
        Atualiza as propriedades de um lead (ex: profissão, motivação, status).
        'updates' deve ser um dicionário como {'Profissão': 'Engenheiro', 'Status': 'Qualificado'}
        """
        if not self.api_key or not self.database_id:
            logger.warning("Credenciais do Notion não configuradas. Serviço desabilitado.")
            return

        page_id = self._find_page_by_phone(phone)
        if not page_id:
            logger.warning(f"Não foi possível encontrar lead com telefone {phone} para atualizar.")
            return

        properties = {}
        for key, value in updates.items():
            if not value:
                continue
            
            # Formatação baseada no nome da propriedade
            if key == 'Status':
                properties[key] = {"status": {"name": str(value)}}
            elif key == 'Nível de Qualificação':
                properties[key] = {"multi_select": [{"name": str(value)}]}
            elif key == 'Link Rápido WhatsApp':
                properties[key] = {"url": str(value)}
            # Para outros campos, assume rich_text
            else:
                properties[key] = {"rich_text": [{"text": {"content": str(value)}}]}

        if not properties:
            logger.info("Nenhuma propriedade para atualizar.")
            return

        update_url = f"{self.api_url}/pages/{page_id}"
        payload = {"properties": properties}

        try:
            response = requests.patch(update_url, headers=self.headers, json=payload)
            response.raise_for_status()
            logger.info(f"Propriedades do lead {phone} atualizadas com sucesso.")
        except Exception as e:
            # Tenta extrair a resposta de erro do Notion para um log mais detalhado
            error_detail = e.response.text if hasattr(e, 'response') else str(e)
            error_message = f"Erro ao atualizar propriedades no Notion para o lead {phone}: {error_detail}"
            logger.error(error_message)
            print(f"[NOTION_SERVICE_ERROR] {error_message}") 