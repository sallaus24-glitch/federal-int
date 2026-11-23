# Coletor inicial — Federal da Sorte (Jogo do Bicho)

Este pacote adiciona um coletor Python ao projeto Federal da Sorte. Ele consulta as fontes ativas cadastradas em `fontes_resultados_bicho`, interpreta páginas públicas suportadas e grava extrações/resultados nas tabelas `extracoes_bicho` e `resultados_bicho`.

## O que esta versão faz

- Consulta fontes ativas com `metodo_coleta = pagina_publica`.
- Adaptadores iniciais para:
  - Hora do Bicho (`horadobicho.com`)
  - Bancas do Bicho (`bancasdobicho.com.br`)
  - O Jogo do Bicho (`ojogodobiicho.com`)
- Mantém banca, data, horário, UF quando identificável, posição e número original.
- Deriva dezena, centena, milhar, grupo e animal usando a tabela padrão dos 25 grupos.
- Evita reimportar extrações já existentes e não sobrescreve resultados anteriores silenciosamente.
- Detecta divergência entre grupo informado na página e grupo calculado pela dezena.
- Grava as novas extrações como `pendente` (ou `divergente` quando há inconsistência). **Não valida resultados automaticamente.**
- Mantém os dados antigos da CAIXA nas tabelas `concursos` e `premios`; não mistura as duas bases.

## Limitações importantes

1. É uma primeira versão de coleta por HTML público. Sites podem mudar o layout, bloquear requisições ou publicar dados corrigidos. O coletor registra erros para que sejam revisados.
2. As fontes `Deu na PT` e `É o Jogo do Bicho` estão cadastradas, mas ainda não possuem adaptador neste pacote. O coletor as ignora com aviso, em vez de tentar interpretar conteúdo sem regra validada.
3. Os agregadores podem replicar os mesmos resultados de uma banca. A deduplicação é por fonte + data + horário + modalidade + identificação da extração. A conciliação entre fontes diferentes ainda precisa de uma etapa própria para comparar cópias da mesma extração.
4. Os resultados são gravados como pendentes para revisão. O site atual filtra extrações `validado`; portanto, nada novo deve aparecer no histórico público até a conferência e validação no painel/SQL.
5. O coletor não aposta, não envia palpites e não faz qualquer transação financeira. É somente ingestão de dados publicados.

## Instalação manual no GitHub

Copie os arquivos deste ZIP para a raiz do repositório `gederal-int`, preservando os caminhos:

- `coletor/coletar_resultados.py`
- `coletor/requirements.txt`
- `.github/workflows/coletar-resultados-bicho.yml`

Não substitua `index.html`, `app.js`, `styles.css` ou outros arquivos existentes.

## Configurar os segredos no GitHub

No repositório: **Settings → Secrets and variables → Actions → New repository secret**.

Crie:

- `SUPABASE_URL` = `https://rrguwmsqjdndtvuclkgw.supabase.co`
- `SUPABASE_SERVICE_ROLE_KEY` = chave `service_role`/secret do projeto Federal da Sorte.

**Nunca coloque a chave service role em `index.html`, `app.js`, `supabase-config.js` ou em qualquer arquivo público.** Ela deve existir somente como GitHub Actions Secret. Não use a chave do projeto MASTER-PRO-AI.

## Primeiro teste

1. Abra **Actions → Coletor Federal da Sorte**.
2. Clique em **Run workflow**.
3. Mantenha `dry_run = true` para simular e ver quantas extrações seriam interpretadas sem gravar no banco.
4. Verifique os logs. Se os resultados interpretados estiverem coerentes, execute novamente com `dry_run = false`.
5. A execução agendada roda a cada 15 minutos e grava apenas registros pendentes/divergentes.

## Verificar no Supabase

```sql
select
  f.nome as fonte,
  e.data_extracao,
  e.horario_local,
  e.identificador_origem,
  e.status_conferencia,
  count(r.id) as total_premios
from public.extracoes_bicho e
join public.fontes_resultados_bicho f on f.id = e.fonte_id
left join public.resultados_bicho r on r.extracao_id = e.id
group by f.nome, e.id
order by e.data_extracao desc, e.horario_local desc;
```

## Regras de segurança e qualidade

- Não há chave privilegiada no código do navegador.
- Não marca automaticamente resultado como validado.
- Não atualiza silenciosamente extração com hash diferente: marca a existente como `divergente`.
- Falhas parciais são registradas como `incompleto`.
- O horário padrão é `America/Sao_Paulo`.
- A extração de cada banca/horário permanece separada.
