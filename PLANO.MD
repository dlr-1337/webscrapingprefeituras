# Plano de Projeto - Robo de Web Scraping de Contatos Publicos de Prefeituras

## 1. Contexto

Cliente: Point C / Eduardo  
Prestador: Otavio Queiroz  
Contratacao e pagamento: plataforma 99Freelas  
Prazo comercial acordado: ate 7 dias apos aprovacao/pagamento e validacao dos insumos  
Entrega principal: arquivo Excel com dados publicos coletados em sites oficiais de prefeituras municipais brasileiras.

## 2. Objetivo

Criar do zero um projeto Python profissional para coletar contatos publicos institucionais de prefeituras municipais brasileiras e gerar uma planilha Excel final, organizada, filtravel e auditavel.

O robo devera:

1. Carregar uma base local de municipios, preferencialmente oficial do IBGE.
2. Filtrar municipios conforme criterios populacionais e capitais definidos.
3. Localizar ou receber sites oficiais das prefeituras.
4. Coletar paginas publicas relevantes sem tecnicas agressivas.
5. Extrair nomes, e-mails, telefones, celulares, cargos e orgaos municipais.
6. Registrar a URL especifica de origem de cada dado encontrado.
7. Registrar pendencias quando dados nao forem encontrados ou houver limitacao tecnica.
8. Gerar um Excel final com abas de resultado, municipios pesquisados, pendencias e resumo.
9. Permitir alteracoes futuras de cargos, secretarias e palavras-chave via arquivos de configuracao.

## 3. Escopo de Municipios

### 3.1 Criterios de inclusao

1. Estado de Sao Paulo:
   - incluir municipios com populacao acima de 30.000 habitantes;
   - incluir capital.

2. Estados MG, SC, PR, RS, RJ, GO, ES, BA e SE:
   - incluir municipios com populacao acima de 15.000 habitantes;
   - incluir capitais.

3. Demais estados brasileiros e Distrito Federal:
   - incluir apenas as capitais.

### 3.2 Fonte da base

A base populacional deve ser fornecida localmente pelo usuario em:

- `data/input/municipios_ibge.xlsx`; ou
- `data/input/municipios_ibge.csv`.

O projeto nao deve depender obrigatoriamente de internet para baixar a base populacional.

### 3.3 Colunas aceitas na base

O carregamento devera aceitar nomes flexiveis de colunas:

- Municipio: `municipio`, `município`, `nome_municipio`, `nome do município`;
- UF/Estado: `uf`, `estado`;
- Populacao: `populacao`, `população`, `habitantes`;
- Capital: `capital`, `is_capital`, `capital_do_estado`;
- Site oficial, quando existir: `site`, `site_oficial`, `url`, `prefeitura_url`.

## 4. Dados a Coletar

Para cada municipio no escopo, procurar dados publicos relacionados a:

1. Prefeito.
2. Vice-prefeito.
3. Chefe de gabinete.
4. Secretario de Desenvolvimento Economico, quando existir.
5. Secretario de Desenvolvimento.
6. Secretario de Financas e/ou Fazenda.
7. Secretario de Planejamento.
8. Agencias municipais de desenvolvimento.
9. Sala do empreendedor ou orgao equivalente ligado a desenvolvimento municipal.

### 4.1 Campos finais

A planilha final deve conter:

- UF;
- Estado;
- Municipio;
- Populacao;
- Criterio de inclusao;
- Site oficial da prefeitura;
- Cargo ou orgao;
- Nome da pessoa, quando disponivel;
- E-mail;
- Telefone;
- Celular;
- URL especifica onde o dado foi encontrado;
- Data da coleta;
- Status da coleta;
- Observacoes.

## 5. Status de Coleta

Usar somente os status abaixo:

- Encontrado;
- Parcial;
- Nao encontrado;
- Site fora do ar;
- Site nao localizado;
- Pagina sem informacao publica;
- Bloqueio tecnico;
- Necessita validacao manual.

## 6. Regras Eticas e Operacionais

1. Coletar apenas dados publicamente disponiveis em sites oficiais ou paginas institucionais.
2. Nao burlar captcha.
3. Nao burlar login.
4. Nao usar tecnicas agressivas.
5. Nao fazer scraping em alta frequencia.
6. Respeitar timeouts, retries moderados e user-agent identificavel.
7. Sempre registrar a URL de origem do dado.
8. Quando nao for possivel associar telefone/e-mail a um cargo especifico, marcar como contato geral ou status Parcial.
9. Nao inventar dados.
10. Se o dado nao estiver disponivel, registrar pendencia.
11. Se houver ambiguidade, manter observacao explicando.
12. Deduplicar contatos repetidos.
13. Garantir que a planilha continue util mesmo com dados faltantes.

## 7. Estrutura Obrigatoria do Projeto

```text
projeto/
├── README.md
├── requirements.txt
├── pyproject.toml
├── .gitignore
├── data/
│   ├── input/
│   │   ├── .gitkeep
│   │   └── README.md
│   ├── output/
│   │   └── .gitkeep
│   └── temp/
│       └── .gitkeep
├── config/
│   ├── cargos.yml
│   ├── estados.yml
│   ├── palavras_chave.yml
│   └── scraping.yml
├── logs/
│   └── .gitkeep
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── carregar_municipios.py
│   ├── filtrar_municipios.py
│   ├── localizar_sites.py
│   ├── coletar_paginas.py
│   ├── extrair_contatos.py
│   ├── normalizar_dados.py
│   ├── gerar_excel.py
│   ├── validar_resultados.py
│   ├── logger.py
│   └── utils.py
└── tests/
    ├── test_filtrar_municipios.py
    ├── test_extrair_contatos.py
    └── test_normalizar_dados.py
```

## 8. Tecnologias

- Python 3.11+;
- `requests`;
- `beautifulsoup4`;
- `pandas`;
- `openpyxl`;
- `pyyaml`;
- `python-dotenv`, se necessario;
- `playwright`, opcional para paginas dinamicas;
- `pytest`.

Evitar dependencias desnecessarias.

## 9. Arquivos de Configuracao

### 9.1 `config/cargos.yml`

Permitir inclusao, remocao e alteracao futura de cargos/secretarias sem reescrever codigo.

Conteudo inicial:

```yaml
prefeito:
  - prefeito
  - prefeita
  - gabinete do prefeito
  - gabinete da prefeita
  - chefe do executivo

vice_prefeito:
  - vice-prefeito
  - vice prefeito
  - vice-prefeita
  - vice prefeita

chefe_gabinete:
  - chefe de gabinete
  - gabinete

desenvolvimento_economico:
  - desenvolvimento econômico
  - secretaria de desenvolvimento econômico
  - indústria e comércio
  - desenvolvimento, indústria e comércio
  - desenvolvimento econômico e turismo
  - trabalho e desenvolvimento econômico

desenvolvimento:
  - secretaria de desenvolvimento
  - desenvolvimento
  - desenvolvimento municipal
  - desenvolvimento urbano

financas_fazenda:
  - finanças
  - fazenda
  - secretaria de finanças
  - secretaria da fazenda
  - administração e finanças
  - finanças e planejamento

planejamento:
  - planejamento
  - secretaria de planejamento
  - planejamento urbano
  - gestão e planejamento
  - planejamento e gestão

agencia_desenvolvimento:
  - agência de desenvolvimento
  - agencia de desenvolvimento
  - desenvolvimento municipal
  - sala do empreendedor
  - banco do povo
  - casa do empreendedor
```

### 9.2 `config/estados.yml`

Deve refletir:

- SP: populacao minima de 30.000 e capital incluida;
- MG, SC, PR, RS, RJ, GO, ES, BA e SE: populacao minima de 15.000 e capital incluida;
- demais UFs e DF: apenas capital.

### 9.3 `config/palavras_chave.yml`

Palavras para busca de paginas internas:

```yaml
palavras_chave:
  - prefeito
  - vice-prefeito
  - gabinete
  - secretarias
  - secretaria
  - equipe
  - administração
  - contatos
  - contato
  - fale conosco
  - desenvolvimento econômico
  - desenvolvimento
  - fazenda
  - finanças
  - planejamento
  - agência de desenvolvimento
  - sala do empreendedor
```

### 9.4 `config/scraping.yml`

```yaml
timeout_segundos: 20
retries: 2
delay_entre_requisicoes: 1.5
max_paginas_por_municipio: 40
usar_playwright_quando_necessario: true
user_agent: "Robo de coleta institucional - contato profissional"
```

## 10. Modulos e Responsabilidades

### 10.1 `src/carregar_municipios.py`

Responsavel por:

- ler XLSX ou CSV;
- detectar encoding em CSV quando possivel;
- normalizar nomes de colunas;
- aceitar variacoes de nomes de municipio, UF, populacao, capital e site;
- validar colunas minimas;
- retornar `pandas.DataFrame` padronizado.

### 10.2 `src/filtrar_municipios.py`

Responsavel por:

- aplicar criterios populacionais por UF;
- incluir capitais conforme regra;
- gerar coluna `criterio_inclusao`;
- salvar `data/output/municipios_filtrados.xlsx`;
- permitir filtros por `--uf`, `--municipio` e `--limite`.

### 10.3 `src/localizar_sites.py`

Responsavel por:

- usar site oficial ja presente na base, quando existir;
- inferir URLs basicas e nao invasivas, quando possivel;
- nao fazer scraping de Google;
- manter campo manual para preenchimento posterior;
- marcar `Site nao localizado` quando nao houver URL confiavel.

### 10.4 `src/coletar_paginas.py`

Responsavel por:

- baixar pagina inicial;
- extrair links internos relevantes por palavras-chave;
- respeitar limite de paginas por municipio;
- evitar arquivos grandes e extensoes irrelevantes;
- capturar texto visivel e URL;
- registrar erros, timeouts, sites fora do ar e bloqueios tecnicos;
- continuar execucao mesmo quando um municipio falhar.

### 10.5 `src/extrair_contatos.py`

Responsavel por:

- extrair e-mails por regex;
- extrair telefones fixos brasileiros;
- extrair celulares brasileiros;
- detectar cargos/orgaos por palavras-chave configuraveis;
- tentar associar contatos a cargo por bloco de texto, proximidade textual ou relevancia da pagina;
- marcar contato geral/parcial quando associacao for fraca;
- nunca inventar nome ou cargo.

### 10.6 `src/normalizar_dados.py`

Responsavel por:

- normalizar UF em maiusculo;
- normalizar municipio em capitalizacao adequada;
- normalizar e-mails em minusculo;
- normalizar telefones quando possivel;
- padronizar cargo/orgao;
- limpar URLs;
- padronizar status;
- remover duplicidades com base em UF, municipio, cargo/orgao, nome, e-mail, telefone e URL especifica.

### 10.7 `src/gerar_excel.py`

Responsavel por:

- gerar `data/output/resultado_final_point_c.xlsx`;
- criar abas obrigatorias;
- aplicar filtro;
- congelar primeira linha;
- ajustar largura de colunas;
- destacar cabecalhos;
- manter planilha limpa e profissional.

### 10.8 `src/validar_resultados.py`

Responsavel por:

- validar colunas obrigatorias;
- validar status permitidos;
- identificar linhas sem URL quando status for encontrado/parcial;
- gerar pendencias estruturadas;
- apoiar testes e revisao final.

### 10.9 `src/logger.py`

Responsavel por:

- configurar logs em `logs/execucao.log`;
- registrar inicio e fim da execucao;
- registrar municipio processado;
- registrar site acessado;
- registrar erros, paginas ignoradas, dados encontrados e pendencias.

### 10.10 `src/main.py`

Responsavel por:

- expor CLI principal;
- orquestrar carregamento, filtro, localizacao, coleta, extracao, normalizacao, validacao e Excel;
- suportar execucao parcial.

Comando principal:

```bash
python -m src.main --input data/input/municipios_ibge.xlsx --output data/output/resultado_final_point_c.xlsx
```

Opcoes obrigatorias:

- `--dry-run`;
- `--somente-filtrar`;
- `--limite 10`;
- `--uf SP`;
- `--municipio "Campinas"`;
- `--sem-playwright`.

## 11. Excel Final

Arquivo:

```text
data/output/resultado_final_point_c.xlsx
```

### Aba 1: Resultado consolidado

Colunas:

- UF;
- Estado;
- Municipio;
- Populacao;
- Criterio de inclusao;
- Site oficial;
- Cargo/Orgao;
- Nome;
- E-mail;
- Telefone;
- Celular;
- URL especifica;
- Data da coleta;
- Status;
- Observacoes.

### Aba 2: Municipios pesquisados

Colunas:

- UF;
- Estado;
- Municipio;
- Populacao;
- Criterio de inclusao;
- Site oficial;
- Status geral;
- Observacoes.

### Aba 3: Pendencias

Colunas:

- UF;
- Municipio;
- Tipo de pendencia;
- Descricao;
- URL, se houver;
- Status;
- Observacoes.

### Aba 4: Resumo

Indicadores:

- Total de municipios no escopo;
- Total de municipios com algum dado encontrado;
- Total de municipios com dados parciais;
- Total de municipios sem dados encontrados;
- Total de sites nao localizados;
- Total de sites fora do ar;
- Total de bloqueios tecnicos;
- Data/hora da execucao.

## 12. Logs

Arquivo:

```text
logs/execucao.log
```

Deve registrar:

- inicio e fim da execucao;
- municipio processado;
- site acessado;
- erros;
- paginas ignoradas;
- dados encontrados;
- pendencias.

## 13. Testes Obrigatorios

Criar testes unitarios para:

1. Filtro de municipios:
   - SP acima de 30.000;
   - UFs MG/SC/PR/RS/RJ/GO/ES/BA/SE acima de 15.000;
   - demais UFs e DF apenas capitais.

2. Extracao:
   - e-mails institucionais comuns;
   - telefones fixos;
   - celulares;
   - contatos proximos a cargos.

3. Normalizacao:
   - telefones;
   - nomes de municipios;
   - UF;
   - e-mails;
   - status.

4. Deduplicacao:
   - contatos repetidos com mesma UF, municipio, cargo/orgao, nome, e-mail, telefone e URL.

5. Estrutura de resultado:
   - colunas obrigatorias;
   - abas basicas do Excel.

Comandos finais esperados:

```bash
pip install -r requirements.txt
pytest
python -m src.main --help
```

## 14. README

O `README.md` deve explicar:

- objetivo do projeto;
- escopo;
- criterios de municipios;
- como instalar;
- como configurar ambiente;
- como adicionar a base IBGE;
- como executar;
- como alterar cargos/secretarias futuras;
- como interpretar a planilha final;
- limitacoes conhecidas;
- regras eticas de scraping.

## 15. Base de Exemplo

Se nao houver base real em `data/input`, criar:

```text
data/input/exemplo_municipios.csv
```

Com municipios controlados apenas para validar funcionamento:

- Sao Paulo/SP;
- Campinas/SP;
- Belo Horizonte/MG;
- Curitiba/PR;
- Florianopolis/SC;
- Rio de Janeiro/RJ;
- Salvador/BA;
- Aracaju/SE;
- Goiania/GO;
- Vitoria/ES;
- Brasilia/DF.

Esses exemplos nao devem ser usados como resultado final real.

## 16. Limitacoes Documentadas

O projeto nao deve prometer encontrar 100% dos dados, pois depende da disponibilidade publica nos sites oficiais.

Documentar que:

- sites fora do ar serao marcados como pendencia;
- sites com captcha serao marcados como bloqueio tecnico;
- sites sem publicacao de contatos especificos serao marcados como nao encontrado ou parcial;
- dados publicados incorretamente pela prefeitura serao registrados conforme a fonte disponivel;
- contatos genericos devem ser marcados como gerais quando nao houver associacao clara a cargo especifico.

## 17. Sequencia de Implementacao

### Fase 1 - Fundacao do projeto

1. Criar estrutura de diretorios obrigatoria.
2. Criar `.gitignore`, `requirements.txt` e `pyproject.toml`.
3. Criar arquivos `.gitkeep`.
4. Criar arquivos YAML de configuracao.
5. Criar `data/input/README.md`.
6. Criar `data/input/exemplo_municipios.csv`.

### Fase 2 - Pipeline de municipios

1. Implementar carregamento XLSX/CSV.
2. Normalizar colunas flexiveis.
3. Aplicar filtros populacionais/capitais.
4. Gerar `municipios_filtrados.xlsx`.
5. Cobrir regras com testes.

### Fase 3 - Localizacao e coleta

1. Consumir site oficial da base, quando existir.
2. Criar inferencia basica de URL oficial.
3. Implementar cliente HTTP com timeout, retry, delay e user-agent.
4. Coletar pagina inicial e links internos relevantes.
5. Limitar paginas por municipio e ignorar arquivos irrelevantes.
6. Registrar pendencias e erros sem interromper todo o pipeline.

### Fase 4 - Extracao e normalizacao

1. Implementar regex de e-mail.
2. Implementar regex de telefones fixos e celulares.
3. Implementar deteccao de cargos por YAML.
4. Implementar associacao por bloco/proximidade textual.
5. Normalizar dados.
6. Deduplicar contatos.
7. Cobrir extracao e normalizacao com testes.

### Fase 5 - Excel e validacao

1. Gerar Excel com quatro abas obrigatorias.
2. Aplicar formatacao profissional.
3. Gerar resumo.
4. Validar colunas, status e URLs de origem.
5. Criar pendencias estruturadas.

### Fase 6 - CLI, logs e documentacao

1. Implementar `python -m src.main`.
2. Adicionar opcoes `--dry-run`, `--somente-filtrar`, `--limite`, `--uf`, `--municipio` e `--sem-playwright`.
3. Configurar logs em `logs/execucao.log`.
4. Escrever README final.
5. Executar comandos de validacao.

## 18. Criterios de Aceite

O projeto sera considerado pronto quando:

1. A estrutura obrigatoria estiver criada.
2. A base de municipios puder ser carregada e filtrada.
3. Os criterios populacionais forem aplicados corretamente.
4. O robo conseguir processar sites de prefeituras.
5. O sistema extrair e-mails, telefones, celulares, nomes e cargos quando disponiveis.
6. A saida Excel for gerada com todas as abas definidas.
7. Pendencias forem registradas corretamente.
8. Houver arquivo de configuracao para incluir/trocar secretarias.
9. Houver logs de execucao.
10. Houver README com instrucoes claras.
11. Houver testes basicos passando.
12. O projeto puder ser executado pelo comando principal.

## 19. Checklist de Revisao Final

- [x] Estrutura de diretorios confere com o escopo.
- [x] `requirements.txt` instala dependencias necessarias.
- [x] `pyproject.toml` define projeto e pytest.
- [x] Configuracoes YAML carregam corretamente.
- [x] `exemplo_municipios.csv` existe e e apenas demonstrativo.
- [x] `python -m src.main --help` funciona.
- [x] `python -m src.main --somente-filtrar --input data/input/exemplo_municipios.csv` gera municipios filtrados.
- [x] Excel final contem as quatro abas.
- [x] Logs sao gerados em `logs/execucao.log`.
- [x] `pytest` passa.
- [x] README documenta instalacao, execucao, limitacoes e regras eticas.

## 20. Evidencias de Execucao

Comandos executados no ambiente local:

```bash
pip install -r requirements.txt
pytest
python -m src.main --help
python -m src.main --input data/input/exemplo_municipios.csv --somente-filtrar
python -m src.main --input data/input/exemplo_municipios.csv --limite 1 --uf SP --municipio Campinas --sem-playwright --output data/output/resultado_final_point_c.xlsx
```

Resultados verificados:

- `pytest`: 7 testes passaram.
- `python -m src.main --help`: CLI exibida com as opcoes obrigatorias.
- `municipios_filtrados.xlsx`: gerado em `data/output/`.
- `resultado_final_point_c.xlsx`: gerado em `data/output/`.
- Abas verificadas no Excel: `Resultado consolidado`, `Municípios pesquisados`, `Pendências`, `Resumo`.
- `logs/execucao.log`: gerado com inicio/fim, municipio processado, site acessado e dados encontrados.
