import logging
import os
from typing import Dict
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class OpenAIService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY não configurada.")
        
        # O cliente agora é assíncrono
        self.client = AsyncOpenAI(api_key=self.api_key)

    async def generate_sales_summary(self, lead_data: Dict) -> str:
        """
        Gera um resumo curto e estratégico sobre o lead para a equipe de vendas.
        """
        lead_name = lead_data.get('Cliente', 'Um novo lead')
        profession = lead_data.get('Profissão', 'não informada')
        motivation = lead_data.get('Real Motivação', 'não informado')

        prompt = f"""
        Você é um gerente de vendas criando uma notificação para sua equipe no WhatsApp.
        Crie uma frase curta, profissional e motivadora sobre um novo lead qualificado.
        Varie o tom e a estrutura da frase a cada vez.

        Dados do lead:
        - Nome: {lead_name}
        - Profissão: {profession}
        - Motivo para aprender inglês: {motivation}

        Exemplos de frases que você pode criar:
        - "Atenção time: Lead quente na área! O(A) {lead_name}, que trabalha como {profession}, quer aprender inglês por motivo de {motivation}. Isso sinaliza urgência, vamos pra cima!"
        - "Nova oportunidade de ouro, equipe! {lead_name} ({profession}) precisa de inglês para {motivation}. Parece um cliente com grande potencial de fechamento."
        - "Alerta de lead qualificado! {lead_name}, que atua como {profession}, está com o objetivo claro de aprender por {motivation}. É a nossa chance de mostrar nosso valor."

        Agora, crie uma nova frase única e inspiradora para este lead, usando os dados fornecidos.
        """
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Você é um gerente de vendas criando uma notificação para sua equipe no WhatsApp."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=150
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Erro ao gerar resumo de vendas com OpenAI: {e}")
            # Mensagem de fallback em caso de erro na API da OpenAI
            return f"Atenção time: Novo lead qualificado! {lead_name} ({profession}) demonstrou interesse em nossos serviços por motivo de {motivation}." 