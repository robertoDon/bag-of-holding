# Guia de ingestão de dados

## Sobre este documento

Este documento tem como objetivo explicar, de forma detalhada, como funciona o processo de
ingestão de dados do catálogo de produtos. Ele foi escrito pensando tanto em quem está
chegando agora no time quanto em quem já trabalha com isso há algum tempo e quer relembrar
os detalhes. Vale a pena ler com calma, porque vários dos pontos abaixo já causaram
problemas no passado e a gente quer evitar que se repitam.

## De onde vêm os arquivos

Os arquivos chegam no formato CSV e são depositados no bucket `s3://ingest-raw/` todos os
dias, por volta das 06:00 (horário de Brasília). É importante lembrar que esse horário pode
variar um pouco dependendo do fornecedor, mas em geral é isso que acontece.

Uma coisa que precisa ficar muito clara: nunca, em hipótese alguma, apague arquivos do
bucket raw. Se um arquivo precisa sair de lá, o correto é mover ele para a pasta
`archive/`. Isso é importante porque a gente precisa conseguir reprocessar qualquer dia do
passado se for necessário.

Os arquivos ficam guardados por 90 dias e depois disso são removidos automaticamente pela
regra de ciclo de vida do bucket, então não é preciso se preocupar com limpeza manual.

## Tamanho e formato

Cada arquivo pode ter no máximo 2 GB. Quando um fornecedor manda um arquivo maior do que
isso, ele precisa ser dividido antes da ingestão, e para isso a gente usa o script
`split_csv.py`, que já está pronto e funciona bem.

As colunas obrigatórias, ou seja, aquelas que precisam estar presentes em todo arquivo sem
exceção, são `sku`, `preco` e `estoque`. Se alguma delas estiver faltando, o arquivo não
vai passar pela validação.

Com relação ao preço, vale reforçar que ele precisa vir em centavos, como número inteiro, e
nunca como float. Em 2026-03-02 um arquivo chegou com o preço em float e isso gerou uma
diferença de R$ 12.400 no fechamento do mês, que demorou bastante para ser encontrada.

## Reprocessamento

Quando for necessário reprocessar um dia, o comando a ser usado é
`ingest run --date AAAA-MM-DD --force`. Note que a opção `--force` sobrescreve os dados que
já foram carregados, e por isso ela só pode ser usada com a aprovação do dono do dataset.
Sem essa aprovação, não use o `--force`.

## Erros

Os erros de validação são enviados automaticamente para o canal #dados-alertas, para que o
time possa acompanhar. Quando um arquivo tem mais de 50 erros, o lote inteiro é rejeitado e
nada daquele arquivo é carregado, mesmo as linhas que estavam corretas.

## Resumo

Resumindo: não apague nada do raw, respeite o limite de tamanho, mande preço em centavos e
só use o `--force` com aprovação. Seguindo isso, a ingestão funciona sem surpresas.
