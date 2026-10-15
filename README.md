# Missal Diário — Paróquia São Sebastião

Site preparado para funcionar sem atualização manual.

## O que ele faz

- abre automaticamente na data atual (fuso de Brasília);
- preserva o histórico de 30/09/2026 a 31/12/2026 e gera novas datas automaticamente **no dia da celebração**;
- usa o Missal Romano CNBB 2023 como base das páginas;
- mantém marcações futuras como **sugestão** quando ainda não há folheto oficial;
- executa verificações diárias às 04h, 04h30, 04h50, 05h, 05h10, 05h30 e 06h (horário de Brasília); o GitHub pode atrasar o início real;
- quando encontra um novo PDF de **O Povo de Deus**, tenta identificar Saudação, Ato Penitencial, Prefácio, Oração Eucarística, aclamação e presença de bênção solene; a página do formulário não é declarada confirmada se não tiver correspondência verificável no folheto;
- só grava alterações quando encontrou informação nova.

## Publicação

Este projeto foi preparado para GitHub Pages.

1. Crie um repositório público.
2. Envie todos estes arquivos para a branch `main`.
3. Em **Settings → Pages**, selecione **GitHub Actions** como fonte.
4. O workflow `Publicar site no GitHub Pages` publicará o endereço.
5. O workflow `Atualizar Missal Diário` gera/revisa dados, consulta folhetos e publica o site automaticamente.

Não é necessária chave de API paga.

## Observação

A leitura automática do folheto usa reconhecimento por texto. Quando o layout do PDF mudar muito, algum item pode continuar marcado como sugestão em vez de ser alterado incorretamente.

## Regra de liberação das datas

- Os dias que já passaram continuam disponíveis para consulta.
- O dia seguinte não aparece antecipadamente.
- À meia-noite, o novo dia ainda permanece bloqueado.
- A preparação automática começa antes das 05h, e há tentativas posteriores como recuperação.
- A rotina pode atualizar `status.js` antes das 05h; o navegador só libera o dia a partir das 05h, caso os dados já tenham sido publicados.
- A seta para a direita fica desativada quando o usuário já está na data mais recente liberada.

## Revisão automática e tentativas de publicação das 05h

A rotina tenta corrigir inconsistências estruturais comuns, mas bloqueia erros que impedem uma publicação responsável e distingue páginas ainda não conferidas.

A ordem é:

1. procura e aplica o folheto oficial quando disponível;
2. revisa os dados litúrgicos cadastrados;
3. corrige automaticamente inconsistências de Saudação, Ato Penitencial, Prefácio, Oração Eucarística, aclamação, bênção e separação rápida;
4. preserva páginas e informações válidas já cadastradas no Missal;
5. quando uma escolha é discricionária, mantém a marcação **sugestão**;
6. atualiza `status.js`, libera o novo dia e publica a versão corrigida.

A automação evita inventar uma página específica da Missa do dia. O calendário atual já está preenchido até 31/12/2026, então as páginas da Fita 2 devem vir do cadastro existente.

## Nomenclatura dos Ritos Iniciais

O site mantém o mesmo padrão usado na separação manual:

- `Saudação A`, `Saudação B`, `Saudação C` etc., sem exibir “Fórmula A”;
- `Ato Penitencial — Primeira fórmula, 1ª/2ª/3ª opção`;
- `Ato Penitencial — Segunda fórmula, 1ª/2ª/3ª opção`;
- `Ato Penitencial — Terceira fórmula, 1ª/2ª/3ª opção`.

As sugestões continuam identificadas como `(sugestão)`.

## Cadastro e liberação diária

O calendário de 2026 permanece guardado como histórico. **Não é necessário cadastrar antecipadamente o ano de 2027:** antes da atualização diária, `scripts/generate_daily.py` consulta uma referência brasileira de liturgia diária para verificar **data, celebração, tempo e cor litúrgica**. Aos sábados, prepara também o domingo. Depois, `update_folheto.py` procura indicações oficiais e `validate_daily.py` revisa o resultado. A fonte litúrgica online **não fornece páginas do Missal Romano**: quando não houver indicação confiável, a Fita 2 exibirá **Página a conferir** em vez de uma página inventada. Se a consulta do dia falhar, a publicação é bloqueada e as próximas tentativas agendadas poderão recuperá-la.

Execuções antes das 05:00 preparam os dados e o status, enquanto o navegador impede a liberação do novo dia antes das 05:00 de Brasília. A pontualidade do início dos trabalhos agendados pelo GitHub Actions não é garantida; a preparação antecipada reduz o risco.



## Regra de responsividade

Toda alteração visual, estrutural ou de navegação feita no site deve ser aplicada e conferida também na versão mobile. Nenhuma melhoria deve ser considerada concluída apenas no layout de computador.

Ao alterar o site:
- manter o comportamento e a identidade visual consistentes entre desktop e celular;
- ajustar tamanhos, espaçamentos, quebras de linha, botões, cartões e animações para telas menores;
- verificar se nenhum texto, número, botão ou elemento fica cortado, sobreposto ou fora da tela no mobile;
- preservar boa legibilidade e facilidade de toque no celular.


## Entrega após alterações

Sempre que houver qualquer alteração no site:
- enviar ao usuário o link público do GitHub Pages;
- gerar e enviar também uma cópia HTML atualizada e autossuficiente para abrir diretamente no ChatGPT;
- manter essa cópia coerente com a versão desktop e mobile publicada.


## Regra permanente: site, mobile e app sempre juntos

Toda alteração futura deve ser tratada como uma única entrega para **site + versão desktop + versão mobile + app/PWA instalado**.

Após qualquer modificação:
- publicar a alteração no GitHub Pages;
- conferir a responsividade no mobile;
- garantir que o app/PWA instalado busque a versão mais recente quando estiver online;
- preservar o funcionamento offline usando a última versão válida em cache;
- atualizar o mecanismo de cache/service worker quando necessário;
- só considerar a alteração concluída depois que a versão publicada estiver disponível.

## Ritos Iniciais

As sugestões mostram somente a frase da Saudação Inicial e a introdução do Ato Penitencial, sem diálogos, respostas da assembleia nem o restante do rito. Quando o PDF do folheto permite leitura verificada, guarda apenas as respectivas frases iniciais; caso contrário, mantém a sugestão e o acesso ao folheto.

- A rotina de folhetos busca também anexos oficiais pelo catálogo público do WordPress e tenta reler os PDFs oficiais conhecidos que ainda não tenham os dois ritos transcritos. Somente marca os ritos como confirmados quando ambos foram extraídos com seus limites de seção reconhecidos.

## Fonte oficial x sugestões

- **Havendo folheto**: cada indicação confirmada do PDF *O Povo de Deus* permanece como oficial. Cada parte **omitida ou não identificada** no folheto recebe uma **sugestão identificada**, com referência de página e título para preparar o Missal.
- **Sem folheto**: mantém sugestões claramente identificadas, sem fingir que são escolhas oficiais.
- **Bênção Solene**: quando o folheto não indica, sugerir uma bênção adequada ao tempo/celebração. Nos domingos do Tempo Comum: *Tempo Comum VI*, p.585. Em celebrações marianas: *Bem-aventurada Virgem Maria*, p.585. A seta da separação rápida inclui a página sugerida.
- **Aclamação da Oração Eucarística**: quando o folheto indica a Oração Eucarística, mas não indica a aclamação, somente a aclamação fica como sugestão. A Oração Eucarística continua identificada como escolha oficial.
- O botão extra de abrir PDF dentro dos Ritos Iniciais permanece removido; a função geral **Folheto dominical** continua disponível.

## Auditoria técnica de 14/10/2026

- A rotina diária gera datas sob demanda; não existe exigência de pré-cadastro anual, mas a identificação das **páginas** do Missal continua condicionada a uma referência conferível.
- Fonte suplementar utilizada apenas para celebração/tempo/cor: `https://carmosaodomingos.com.br/liturgia` (paróquia que apresenta dados com referência à CNBB). Prioridade das escolhas: folheto oficial `O Povo de Deus` da Arquidiocese.
- Fitas cuja escolha não consta do folheto recebem **sugestão**, nunca rótulo de indicação oficial. A Fita 2 só é confirmada como página oficial se o código encontrar o mesmo número referenciado no PDF; caso contrário, mostra a necessidade de conferência.
- O Service Worker armazena no máximo uma cópia por arquivo essencial, independentemente dos parâmetros usados na URL, e ignora PDFs e outros recursos externos.
- O texto copiado não contém identificadores técnicos internos. O site ganhou foco visível e legendas maiores no menu mobile.
- A publicação às 05h depende do agendamento GitHub Actions; atrasos externos não podem ser eliminados por software. Há várias execuções programadas de recuperação.
- As auditorias com Playwright verificam dimensões de tela Android, WebKit (motor do Safari), desktop e tablet; **emulação não substitui testes em aparelhos físicos**.


## Controles adicionais de publicação, responsividade e exportação

- O workflow comum de GitHub Pages recalcula um token de versão baseado no conteúdo, atualiza o Service Worker e gera uma cópia autossuficiente antes do deploy.
- Após o deploy, `scripts/check_publication.py` compara a **data** e o **token de versão** entre os arquivos locais e a página pública. Um HTTP 200 isolado não basta para considerar a publicação concluída.
- A auditoria visual mobile roda após modificações relevantes no site; a auditoria completa percorre também tablet, desktop, calendário, modo celebração, cópia, criação de PNG, folheto direto e comportamento offline do PWA.
- Em larguras de até 950 px, o calendário funciona como painel central com altura limitada e rolagem interna, inclusive com o aparelho deitado.
- A exportação em imagem e o painel **Preparar o Missal** distinguem escolha sugerida, página ainda não conferida e página não indicada.
- O status `requires-missal-page-check` significa que a data foi cadastrada, mas uma ou mais páginas do Missal precisam de referência externa. **Não é confirmação litúrgica completa.**
- Nenhuma execução agendada do GitHub Actions tem garantia de começar exatamente no minuto configurado. Executar antes das 05h reduz o risco de atraso, mas não elimina o risco de falha na plataforma.
- Não há fonte online confiável de correspondência completa de **todas as páginas** da edição CNBB 2023 do Missal para cada celebração futura. Na ausência de correspondência verificada, o site informa **Página a conferir** em vez de inventar uma referência.
- O HTML público autossuficiente é acessível pelo arquivo `Missal-Diario-Standalone.html` no próprio GitHub Pages.


## Referência do Missal Romano 2023 enviada ao ChatGPT

O exemplar integral do **Missal Romano, terceira edição típica em português (CNBB, 1ª impressão 2023)** enviado pelo responsável foi inspecionado nesta auditoria: **1.270 páginas**. Identificação do arquivo por SHA-256: `2ca10b5555dfb02f636cdd7db815ae198539c9a0b506ab9cdfc85670ea951a62`.

- O documento integral **não está anexado a este repositório público**: trata-se de livro protegido por direitos autorais e sua publicação integral não deve ocorrer sem a permissão do titular. O repositório armazena apenas metadados bibliográficos e as referências necessárias no `missal-reference-index.json`.
- O verificador `scripts/check_missal_references.py` roda em toda publicação do GitHub Pages e em cada atualização diária. Compara os números de páginas com o índice verificado e com o tipo de fita; bloqueia números fora do índice, seções incompatíveis e separações rápidas divergentes.
- A conferência do PDF completo pode ser repetida localmente com `MISSAL_ROMANO_PDF=/caminho/para/arquivo.pdf python scripts/check_missal_references.py`. O script confere a integridade criptográfica SHA-256 sem enviar o conteúdo do arquivo para o site.
- **Duas correções decorrentes de exame direto do PDF:** o prefácio próprio da Dedicação da Basílica do Latrão inicia na **p. 852** (não 851); o da Imaculada Conceição inicia na **p. 873** (não 872).
- O índice atual cobre páginas usadas nos dados cadastrados e não substitui identificação litúrgica completa para qualquer data futura. Para páginas novas não identificadas, usar **Página a conferir** em vez de apresentar uma referência sem base confirmada.

## Melhorias de interação (outubro de 2026)

- Os cartões da imagem de compartilhamento calculam a altura do título antes de iniciar as descrições, evitando sobreposição em títulos de duas ou mais linhas.
- No calendário mobile, o foco passa ao comando interno de fechar, com retorno ao seletor de data, controle da tecla Escape e navegação Tab dentro da janela.
- A tela inicial exibe os dados principais sem transição que os deixe invisíveis no primeiro instante do Safari.
- Em páginas com quatro alternativas (como o Natal), a separação rápida mobile apresenta os quatro números organizados em uma grade 2×2, preservando os valores.
- A Missa de **24/12** requer escolha explícita entre manhã, Vigília e visão geral; o sistema não escolhe automaticamente com base no horário das 12h.

## Correções de 15/10/2026 — rastreabilidade, telas e PWA

- **Escolha de 24 de dezembro:** visão geral fica selecionada por padrão, inclusive após 12h; Missa da manhã e Vigília só alteram páginas, título e cor quando o usuário escolhe explicitamente.
- **Ciclo sem indicação:** quando o cadastro apresenta `—`, o site informa "Não se aplica" e rotula o campo de modo neutro.
- **Controles mobile:** botões de navegação, calendário, ações e seleção do Natal ganharam alvos de toque de pelo menos 44 px quando compatível com o espaço.
- **Índice litúrgico por data:** `missal-date-formulary-map.json` associa as 93 datas cadastradas às páginas específicas dos formulários do Missal, usando o exemplar CNBB 2023 conferido. `scripts/check_missal_references.py` impede que páginas sejam trocadas por outra da mesma seção em datas indexadas, e registra alerta para datas futuras sem correspondência conferida.
- **PDF original:** o arquivo completo não foi distribuído no repositório público porque seria necessário verificar autorização de redistribuição. A cópia do responsável continua disponível em sua Biblioteca pessoal do ChatGPT; o identificador SHA-256 presente nos metadados assegura que a referência é a edição verificada. O GitHub Actions não possui acesso automático a arquivos particulares da Biblioteca e não reabre esse PDF a cada publicação.
- **Folhetos novos:** o mesmo workflow passa a consultar também às 11h, 16h e 20h (horário de Brasília). O GitHub pode iniciar o agendamento com atraso.
- **Ícones PWA:** os PNGs 180, 192 e 512 px são gerados do SVG do projeto antes da publicação; o manifesto apresenta opções PNG/SVG e o ícone Apple usa PNG. A verificação do deploy também confirma os três PNGs públicos.
- **Links antigos:** os arquivos `missal-atualizado-v54.html` até `v57.html` redirecionam para o site atual, evitando distribuir interfaces defasadas e preservando os URLs.
- **Regressões:** `full-site-audit.cjs` inclui simulação dos horários de 24/12, confirmação do botão selecionado, cor e páginas das opções.

Estas verificações aumentam a segurança, mas não garantem acerto litúrgico absoluto: escolhas pontuais do folheto, páginas novas e celebrações alternativas ainda exigem referência oficial independente. Na ausência de página confirmada, a interface deve informar **Página a conferir**, não inventar numeração.

## Correções concluídas após auditoria de 15/10/2026

- **Bênçãos opcionais do Missal Romano 2023, conferidas no PDF original**: 28/10 (Santos Simão e Judas, p. 586 conforme formulário p. 840), 02/11 (Fiéis Defuntos, p. 588 conforme formulários p. 846–848), 30/11 (Santo André, p. 586 conforme formulário p. 866), 12/12 (Nossa Senhora de Guadalupe, p. 585 conforme formulário p. 876). As quatro permanecem sugestões quando não existir folheto oficial. **Prioridade do folheto preservada.**
- **Referência independente**: `missal-rubrics-verified.json` guarda apenas metadados das remissões próprias do livro, sem reproduzir o texto da obra; `scripts/check_missal_references.py` passa a impedir que alterações futuras troquem essas bênçãos por outra página válida, salvo indicação diferente no folheto oficial.
- **Teclado e leitor de telas**: o menu Mais é diálogo semântico, com navegação circular por Tab/Shift+Tab, foco devolvido ao botão original no fechamento e Escape funcionando.
- **Marcação rápida responsiva**: as cinco fitas permanecem centralizadas em cinco colunas, com fonte mínima melhorada e coluna maior em datas com quatro alternativas. O layout é verificado em tamanhos Android e iPhone.
- **Marcos de página e SEO**: `<main>` e `<footer>` semânticos, descrição, canonical e Open Graph. O arquivo `sitemap.xml` está disponível para submissão à busca; `robots.txt` nesta pasta só serve como documentação, pois regras efetivas de rastreamento precisam estar na raiz de `macflayyy.github.io`, fora do escopo do GitHub Pages deste projeto.
- **Desempenho**: a imagem original da paróquia saiu do HTML principal (menos cerca de 190 KB de código Base64) e agora é `brand-logo.png` com cache separado pelo service worker. O arquivo HTML autossuficiente ainda inclui a logomarca para funcionar localmente e no chat.
- **PWA offline**: logo e ícones PNG de instalação passam a integrar o cache. Os testes verificam carregamento da versão pública e funcionamento offline.
- **Transparência de atualização**: o rodapé identifica o horário exibido como o momento da **preparação inicial do dia**, não como a hora da última verificação ou como garantia de publicação exatamente às 05h.

**Limitações remanescentes**: o workflow do GitHub não pode abrir diretamente o PDF privado guardado na Biblioteca do ChatGPT e o GitHub Actions não garante início pontual dos crons. O índice confirmado pelo PDF reduz divergências das datas cobertas, mas a confirmação de novos dias e orientações específicas requer consulta à edição de 2023 ou ao folheto apropriado. O site público não distribui o livro integral por direitos autorais.

## Revisão litúrgica e acessibilidade de 15/10/2026

- **Advento 2026:** o calendário do dia 30/11 (festa de Santo André) mantém o tempo litúrgico Advento e cor própria da festa. O verificador calcula os quatro domingos do Advento para conferir o tempo de todas as datas cadastradas.
- **Natal:** a Missa da Vigília (p. 126) pertence à tarde de 24/12 e foi removida das alternativas da data civil 25/12. No dia 25 permanecem Noite (p. 128), Aurora (p. 130) e Dia (p. 132).
- **Fiéis Defuntos:** a Fita 2 apresenta os três formulários facultativos (p. 846, 847 e 848) conforme o Missal CNBB 2023. A sugestão de bênção própria na p. 588 continua.
- **Recuperação:** o `calendar_seed.json` contém as aberturas curtas de Saudação/Ato Penitencial dos 93 dias registrados, em vez de placeholders genéricos. Os testes comparam esse backup aos registros sem folheto oficial.
- **Conferência editorial:** a associação entre páginas e datas é verificada por regras específicas adicionais; datas futuras ainda podem exigir conferência individual do Missal e folheto. O PDF integral permanece privado e não é distribuído em repositório público.
- **Acessibilidade:** calendário desktop e mobile usam foco inicial e ciclo de Tab, foco restaurado na escolha do dia e anúncio discreto da mudança de celebração via `aria-live`.
- **Desempenho:** verificação de liberação às 05h por temporizador de transição + confirmação periódica; imagem da paróquia otimizada como WebP de qualidade 88 com PNG como fallback e versão incorporada no arquivo HTML autossuficiente.
- **CSS:** as 17 camadas contíguas de estilos foram consolidadas em uma só, preservando a ordem da cascata, para evitar diferenças visuais. Regras antigas ainda têm substituições `!important`; remoções indiscriminadas seriam arriscadas.
- **SEO:** índice principal tem `meta robots`, descrição e URL canônica. O arquivo `robots.txt` do subdiretório não substitui `https://macflayyy.github.io/robots.txt`, que precisaria ser mantido na raiz do host.
- **Visibilidade futura:** o controle no site é de interface. Como `data.js` e `calendar_seed.json` são públicos no GitHub Pages/repositório, não há sigilo técnico sobre dias ainda não liberados; isso exigiria migrar a fonte de dados para hospedagem privada.
- **Status:** `validationDetails` diferencia a conferência estrutural/numérica da consulta integral ao PDF (que não é executada automaticamente no GitHub).
