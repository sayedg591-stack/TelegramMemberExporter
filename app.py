import asyncio
import random
import streamlit as st
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.types import InputPeerUser  
from telethon.errors import FloodWaitError

# Lista de 3 contas para distribuir a carga
contas = [
    {
        "nome": "primeira",
        "api_id": 24370467,
        "api_hash": "3bd6c9abcc93bb25d5ce83ac050cdbfd",
        "string_session": "1AZWarzMBu2zQBXYjFJrLMlwnpycPd8S4xwjMdGyZHyuRCRvUhL_bDbJ8r8p8rpBWAYH_tDJP9_2Ooq6wq2PqcQMpQfTK1UYPP7B2FLApB84r99iKQu5KkEDDsB09yFeKtbaTPcSRkLQ4lzJ2kMGyVyx1FZQu1iowVg39olVAaN9c8cL0FjnBup_tFQ5zlzO4dR09EevEcVhNzbsiS_VH-qkNIt_9B7hKIQc81OtiiDXdzosn5ooAek28JKpsCJbRcy9oIjdWIJOzVMR0BuqUSilkmNdYgNKl_iAmKsGWsMCOXVH0ILVIuUE2awCX-UCueJBuKHw2B52NEPia3PHTS17McKQq5Tk=",
    },
    {
        "nome": "segunda",
        "api_id": 24108269,
        "api_hash": "44d5d76acf1c429d204da9eae95aea43",
        "string_session": "1AZWarzMBu60BiRpACKTZs83I5NVP5vjiusludQS0VPBD2tGCynFCzOfnXbcBfLTD_uUHDd0DhJTpiCgQ_KIvkQbcy9rK1V0SikwmQDAqeLYAyJaQCcUXsU-ZvKsmuihmh_MmT_m2yIMSZM_h2-BXbQKMG4b_CW4IqNDNW6mLs2OrIN8poZIxxajPlh7IvPxtc-aWgrVwrYA10iUHqtj63g0yR7hlOGeisNJfllgXi0Eaw81qn8ldPZJ_sMnIpUmg1Y2N2hIIoTZZmPqbJcCmDG8SizKPty1sAgBGkB9VrJsLVdRUYuWGpxAXbr248VZFvQDEnlvY1V5Dfyo4mfU2LbFKcXbXdys=",
    },
    {
        "nome": "terceira",
        "api_id": 29445826,
        "api_hash": "4095285b92ca3173cff9b21fedda514a",
        "string_session": "1AZWarzMBu2PuAl-AHNzen6De-qfFLa19BXCaOD4gC4IoLXxUSR_-Jn_WpFrizaW4bXQ8yH4Z0EACmH_1V6dWlfMvdfz3c13EvQOOcgrERAmG_Lb9DRU9dMRKdiq82XOCAWEcaNmW-wz_a0ji-Wi1gUEU2oJb1naVABDLhlZn_5-gFv9P6eJHa6uvwRC5xm8i22Y3ZwXgrWfe7vZjEV2w8FY6ZAkgQOl1oVhztvvvhtYMG3GjaAG8ITKLsuIjkX68lhamVjBzYwr-NC6SvlVLt6-d49zAAVJcYP8NBuQRIRXjtYr_cpi1aELp0-u_zRCP60Ybdw7xnyxd3Twwm_X-aTGBzEGz5_w=",
    }
]

# Configurações de segurança aprimoradas
CONFIG = {
    'max_attempts': 3,  # Tentativas por lote antes de desistir
    'base_delay': 300,  # 5 minutos de delay base entre lotes
    'random_delay': 300,  # 5 minutos adicionais aleatórios (total 5-10 min)
    'max_batch_size': 7,  # Reduzido para 7 membros por lote
    'recovery_time': 3600,  # 1 hora de espera se houver FloodWait
    'daily_limit': 150,  # Limite diário por conta (reduzido)
    'account_rotation_delay': 600,  # 10 minutos entre troca de contas
    'max_sessions_per_day': 3  # Máximo de ciclos por conta por dia
}


async def get_entity(client, link):
    """Obtém a entidade (grupo/canal) a partir do link"""
    try:
        if isinstance(link, str):
            if link.startswith('https://t.me/'):
                link = link.split('https://t.me/')[-1]
            entity = await client.get_entity(link)
            return entity
        return link
    except Exception as e:
        st.error(f"Erro ao obter entidade: {e}")
        return None


async def safe_invite(client, destino_entity, users, nome_conta):
    """Tenta adicionar usuários com tratamento de erros robusto"""
    attempts = 0
    while attempts < CONFIG['max_attempts']:
        try:
            await client(InviteToChannelRequest(
                channel=destino_entity,
                users=[InputPeerUser(user.id, user.access_hash) for user in users if user.access_hash]
            ))
            return True
        except FloodWaitError as e:
            wait_time = e.seconds + 120  # Adiciona 2 minutos de margem
            st.warning(f"⏳ {nome_conta}: FloodWait detectado. Esperando {wait_time // 60} minutos...")
            await asyncio.sleep(wait_time)
            attempts += 1
        except Exception as e:
            st.error(f"❌ {nome_conta}: Erro ao adicionar membros: {str(e)}")
            await asyncio.sleep(60)
            attempts += 1
    return False


async def extrair_membros(cliente, grupo_origem, grupo_destino, nome_conta, progress_bar, session_count):
    try:
        # Verificar se já atingiu o limite diário de sessões
        if session_count >= CONFIG['max_sessions_per_day']:
            st.warning(f"⚠️ {nome_conta}: Limite diário de sessões atingido (3)")
            return 0, 0

        # Obter as entidades
        origem_entity = await get_entity(cliente, grupo_origem)
        if not origem_entity:
            st.error(f"❌ {nome_conta}: Grupo de origem não encontrado")
            return 0, 0

        destino_entity = await get_entity(cliente, grupo_destino)
        if not destino_entity:
            st.error(f"❌ {nome_conta}: Grupo de destino não encontrado")
            return 0, 0

        # Verificar permissões
        try:
            await cliente.get_participants(origem_entity, limit=1)
        except Exception as e:
            st.error(f"❌ {nome_conta}: Sem permissão no grupo de origem: {e}")
            return 0, 0

        # Obter membros
        membros_origem = []
        try:
            async for user in cliente.iter_participants(origem_entity, aggressive=True):
                if not user.bot and not user.is_self and not user.deleted:
                    membros_origem.append(user)
                    if len(membros_origem) >= CONFIG['daily_limit']:
                        break  # Limite diário por conta
        except Exception as e:
            st.error(f"❌ {nome_conta}: Erro ao obter membros: {e}")
            return 0, 0

        if not membros_origem:
            st.warning(f"⚠️ {nome_conta}: Nenhum membro encontrado")
            return 0, 0

        st.success(f"✅ {nome_conta}: {len(membros_origem)} membros listados")

        # Processar em lotes
        success_count = 0
        fail_count = 0
        progress_bar.progress(0)
        status_text = st.empty()

        for i in range(0, len(membros_origem), CONFIG['max_batch_size']):
            batch = membros_origem[i:i + CONFIG['max_batch_size']]
            status_text.text(f"⚙️ {nome_conta}: Processando lote {i // CONFIG['max_batch_size'] + 1}...")

            if await safe_invite(cliente, destino_entity, batch, nome_conta):
                success_count += len(batch)
                st.success(f"✅ {nome_conta}: Lote de {len(batch)} adicionado")
            else:
                fail_count += len(batch)
                st.error(f"❌ {nome_conta}: Falha no lote de {len(batch)}")

            # Atualizar progresso
            progress = min((i + CONFIG['max_batch_size']) / len(membros_origem), 1.0)
            progress_bar.progress(progress)

            # Delay aleatório entre lotes (5-10 minutos)
            if i + CONFIG['max_batch_size'] < len(membros_origem):
                delay = CONFIG['base_delay'] + random.randint(0, CONFIG['random_delay'])
                status_text.text(f"⏳ {nome_conta}: Esperando {delay // 60} minutos...")
                await asyncio.sleep(delay)

        return success_count, fail_count

    except Exception as e:
        st.error(f"❌ Erro inesperado em {nome_conta}: {e}")
        return 0, 0


async def main():
    st.title("📲 Transferência Segura de Membros (3 Contas)")
    st.warning("⚠️ Sistema com rotação automática entre 3 contas e intervalos de 10 minutos")

    # Exibir configurações
    st.sidebar.header("⚙️ Configurações de Segurança")
    st.sidebar.write(f"🔒 Membros por lote: {CONFIG['max_batch_size']}")
    st.sidebar.write(f"⏱️ Delay entre lotes: 5-10 minutos")
    st.sidebar.write(f"🔄 Delay entre contas: 10 minutos")
    st.sidebar.write(f"📅 Limite diário: {CONFIG['daily_limit']} por conta")
    st.sidebar.write(f"♻️ Máximo de ciclos: {CONFIG['max_sessions_per_day']} por conta")

    # Links dos grupos
    grupo_origem = st.text_input("🔗 Grupo de Origem (ex: @grupo_origem ou https://t.me/grupo_origem):")
    grupo_destino = st.text_input("🔗 Grupo de Destino (ex: @grupo_destino ou https://t.me/grupo_destino):")

    if not grupo_origem or not grupo_destino:
        st.error("❌ Preencha ambos os links")
        return

    if st.button("▶️ Iniciar Transferência com Rotação Automática"):
        progress_bar = st.progress(0)
        status_container = st.empty()
        total_success = 0
        total_fail = 0
        session_counts = {conta['nome']: 0 for conta in contas}  # Contador de sessões por conta

        # Loop principal de rotação entre contas
        while True:
            for conta in contas:
                if session_counts[conta['nome']] >= CONFIG['max_sessions_per_day']:
                    continue  # Pula contas que já atingiram o limite

                status_container.subheader(f"🔄 Conectando {conta['nome']}...")
                try:
                    async with TelegramClient(
                            StringSession(conta["string_session"]),
                            conta["api_id"],
                            conta["api_hash"]
                    ) as cliente:
                        me = await cliente.get_me()
                        status_container.success(f"✅ {conta['nome']} conectada como @{me.username or 'sem username'}")

                        success, fail = await extrair_membros(
                            cliente,
                            grupo_origem,
                            grupo_destino,
                            conta['nome'],
                            progress_bar,
                            session_counts[conta['nome']]
                        )
                        total_success += success
                        total_fail += fail
                        session_counts[conta['nome']] += 1

                        # Verificar se todas as contas atingiram o limite diário
                        if all(count >= CONFIG['max_sessions_per_day'] for count in session_counts.values()):
                            status_container.info("ℹ️ Limite diário atingido para todas as contas")
                            st.success(
                                f"🎉 Transferência concluída! Total: {total_success} adicionados, {total_fail} falhas")
                            return

                        # Espera de 10 minutos entre contas
                        if conta != contas[-1] or total_success == 0:  # Não esperar após última conta se nenhum sucesso
                            status_container.text(f"⏳ Aguardando 10 minutos antes da próxima conta...")
                            await asyncio.sleep(CONFIG['account_rotation_delay'])

                except Exception as e:
                    status_container.error(f"❌ Erro na conta {conta['nome']}: {e}")
                    continue

            # Verificação para sair do loop se nenhum membro foi adicionado
            if total_success == 0 and all(count > 0 for count in session_counts.values()):
                status_container.error("❌ Nenhum membro foi adicionado após tentar todas as contas")
                break

        st.success(f"🎉 Transferência concluída! Total: {total_success} adicionados, {total_fail} falhas")


if __name__ == "__main__":
    asyncio.run(main())
