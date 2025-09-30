
# Cartão Fidelidade — Cafeteria (Streamlit + SQLite)

Este é um app simples de fidelidade para cafeterias. Com ele, você:
- Cadastra clientes (nome, telefone, e-mail)
- Registra compras e concede **carimbos** automaticamente (ex.: 1 carimbo a cada R$ 10)
- Mostra um **cartão visual** de carimbos
- **Resgata prêmios** quando o cliente atinge o número de carimbos configurado
- Acompanha métricas no painel Admin

## Como executar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

O banco de dados `data.db` será criado automaticamente no primeiro uso (SQLite).

## Regras do programa
- Em **Admin**, ajuste:
  - `Carimbos necessários para prêmio` (padrão: 10)
  - `R$ por carimbo` (padrão: 10 → 1 carimbo a cada R$ 10)

## Deploy (site recomendado)
- **Streamlit Community Cloud**: crie um repositório no GitHub com estes arquivos e publique em https://streamlit.io/cloud (conecte sua conta GitHub e selecione o repo).

> Observação: em hospedagens gratuitas, o arquivo `data.db` pode ser **efêmero** (perde dados em reinicializações). Para produção, use um banco gerenciado (ex.: Supabase, Neon, Planetscale, etc.) e ajuste a camada de persistência.
