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

    async def generate_sales_message(self, lead_data: Dict) -> str:
        """
        Gera uma mensagem para a equipe de vendas usando o ChatGPT com base nos dados do lead.
        
        Args:
            lead_data (Dict): Dados do lead do Notion
            
        Returns:
            str: Mensagem personalizada gerada
        """
        # Criar o prompt com os dados disponíveis
        prompt = f"""
        Você é um assistente de vendas especializado em escolas de inglês.
        
        Analise os dados do lead e crie um resumo estratégico para a equipe de vendas:
        
        Dados do lead:
        - Nome: {lead_data.get('Cliente', '')}
        - Profissão: {lead_data.get('Profissão', 'Não informado')}
        - Objetivo: {lead_data.get('Objetivo', 'Não informado')}
        - Histórico Inglês: {lead_data.get('Histórico Inglês', 'Não informado')}
        - Real Motivação: {lead_data.get('Real Motivação', 'Não informado')}
        - Idade: {lead_data.get('Idade', 'Não informado')}
        - Indicação: {lead_data.get('Indicação', 'Não informado')}
        
        Crie uma análise para a equipe de vendas, incluindo:
        1. Principais pontos de atenção sobre o perfil
        2. Possíveis objeções que podem surgir
        3. Sugestões de abordagem baseadas no perfil
        4. Use emojis para destacar pontos importantes
        5. Use formatação do WhatsApp (*negrito*)
        6. Mantenha a análise objetiva e estratégica
        7. Destaque informações relevantes para conversão
        8. Sugira pacotes ou abordagens específicas para este perfil
        """
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Você é um analista de vendas especializado em escolas de inglês."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Erro ao gerar mensagem de vendas com OpenAI: {e}")
            # Em caso de erro, retorna uma mensagem padrão
            return (
                f"🎯 *Novo Lead Qualificado*\n\n"
                f"👤 Nome: {lead_data.get('Cliente', '')}\n"
                f"💼 Profissão: {lead_data.get('Profissão', 'Não informado')}\n"
                f"🎯 Motivo: {lead_data.get('Real Motivação', 'Não informado')}\n\n"
                "⚠️ Análise do ChatGPT indisponível no momento."
            ) 