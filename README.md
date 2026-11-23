# Federal da Sorte — Jogo do Bicho

Versão inicial do painel estatístico nacional, com foco em resultados históricos do Jogo do Bicho por fonte/banca, modalidade, UF, município e horário.

## O que esta entrega contém

- Interface responsiva para computador e celular.
- Conexão com o projeto Supabase exclusivo `federal-da-sorte`.
- Leitura apenas de extrações com `status_conferencia = validado`.
- Filtros por UF, fonte, modalidade e período.
- Histórico das extrações e distribuição dos 25 grupos.
- Categorias estatísticas: TOP 10, recorrentes, menos recorrentes, tendência recente, equilibradas, adaptativa e alternativas.
- Leituras por grupo, dezena, centena e milhar.
- Preservação dos dados antigos da CAIXA: o aplicativo não consulta nem altera as tabelas legadas `concursos` e `premios`.

## Publicação manual no GitHub Pages

1. Faça backup do repositório atual.
2. Extraia o ZIP.
3. Publique os arquivos e pastas desta entrega na raiz do repositório `gederal-int`.
4. Mantenha o GitHub Pages apontado para a branch/pasta que já publica o site.
5. Abra a URL do site e teste no computador e no celular.

Não é necessário npm para executar esta versão. Para testar localmente, use um servidor HTTP simples (por exemplo, a extensão Live Server do VS Code). Abrir `index.html` diretamente por `file://` pode bloquear módulos JavaScript.

## Supabase já configurado

Projeto: `federal-da-sorte`  
Ref: `rrguwmsqjdndtvuclkgw`  
URL: `https://rrguwmsqjdndtvuclkgw.supabase.co`

A chave `sb_publishable_...` em `supabase-config.js` é uma chave pública apropriada para o navegador. Nunca coloque uma chave `service_role` ou `secret` nesse arquivo, no GitHub ou em qualquer frontend.

O frontend usa somente SELECT nas tabelas de catálogo, extrações validadas e resultados. As políticas RLS do banco controlam o que pode ser lido. Não há escrita pelo navegador nesta versão.

## Importante: dados e fontes

O catálogo de fontes está inicialmente vazio. Nenhum resultado foi raspado ou importado automaticamente nesta entrega. As páginas públicas encontradas anteriormente são agregadores não oficiais; devem ser verificadas quanto à precisão, estabilidade, termos de uso e duplicidade antes de qualquer coleta automática.

O fluxo correto é:
1. Cadastrar cada fonte/banca separadamente.
2. Importar os resultados mantendo URL, data, horário, UF/município e payload original.
3. Conferir os resultados.
4. Marcar a extração como `validado` somente após conferência.
5. O painel passa a incluir a extração nas análises.

Não misture resultados de bancas, horários, estados ou modalidades diferentes como se fossem uma única extração.

## Regras estatísticas

- O painel calcula frequências descritivas no histórico disponível.
- O índice de 0 a 100 é um ranking relativo dentro da amostra e dos filtros selecionados; não é probabilidade de premiação.
- A aba de tendência usa uma janela recente aproximada de 30% da amostra disponível.
- A amostra é ordenada por data/hora da extração para exibição. Para análises formais futuras, recomenda-se incluir desempate estável por fonte, modalidade e identificador da extração.
- Resultados aleatórios não podem ser previstos com garantia. Nenhuma categoria deve ser apresentada como promessa de acerto.

## Estrutura

- `index.html`, `styles.css`, `app.js`: aplicação web.
- `supabase-config.js`: URL e chave publicável.
- `scripts/fontes-candidatas.json`: fontes candidatas para avaliação humana.
- `scripts/modelo-importacao.json`: exemplo de formato canônico de importação.
- `.github/workflows/verificar-site.yml`: verificação simples de disponibilidade do site, sem coletar resultados.

## Próximas etapas recomendadas

1. Confirmar que o frontend conecta ao Supabase e carrega os catálogos.
2. Cadastrar e validar as fontes reais.
3. Implementar importador seguro no lado servidor e revisão humana.
4. Construir backtest walk-forward por série homogênea (mesma banca, modalidade e horário).
5. Adicionar autenticação e área administrativa antes de permitir cadastro/validação pelo painel.

## Observação legal e operacional

Este software é um painel de organização e análise estatística de informações. Não inclui apostas, pagamentos, intermediação ou instruções para operar bancas.
