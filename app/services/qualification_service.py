import logging
import os
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class QualificationService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OPENAI_API_KEY não configurada. A qualificação de profissão será desativada.")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=self.api_key)

        self.high_prio_keywords = ["viagem", "trabalho", "mudar de país", "oportunidade"]
        self.low_prio_keywords = ["aprimorar", "melhorar", "hobby"]

    async def _is_high_income_profession(self, profession: str) -> bool:
        """Usa o GPT para determinar se uma profissão é provavelmente de alta renda."""
        if not self.client or not profession:
            return False

        try:
            prompt = f"A profissão '{profession}' é geralmente considerada de alta renda no Brasil? Responda apenas 'Sim' ou 'Não'."
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3,
                temperature=0,
            )
            answer = response.choices[0].message.content.strip().lower()
            logger.info(f"Análise da profissão '{profession}' para qualificação: {answer}")
            return "sim" in answer
        except Exception as e:
            logger.error(f"Erro ao analisar profissão com OpenAI: {e}")
            return False

    async def classify_lead(self, motivo: str, profissao: str) -> str:
        """Classifica um lead como 'Alto' ou 'Baixo' com base nas regras de negócio."""
        motivo_lower = motivo.lower()

        # Regra 1: Palavras-chave de alta prioridade no motivo
        if any(keyword in motivo_lower for keyword in self.high_prio_keywords):
            logger.info(f"Lead classificado como 'Alto' por palavra-chave no motivo: '{motivo}'")
            return "Alto"

        # Regra 2: Profissão de alta renda
        if await self._is_high_income_profession(profissao):
            logger.info(f"Lead classificado como 'Alto' por profissão: '{profissao}'")
            return "Alto"
        
        # Regra 3: Motivo vago de baixa prioridade
        if any(keyword in motivo_lower for keyword in self.low_prio_keywords):
            if not any(hp_keyword in motivo_lower for hp_keyword in self.high_prio_keywords):
                logger.info(f"Lead classificado como 'Baixo' por motivo vago: '{motivo}'")
                return "Baixo"

        # Classificação padrão
        logger.info("Nenhuma regra específica aplicada. Classificando como 'Baixo' por padrão.")
        return "Baixo" 