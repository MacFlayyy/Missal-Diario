# Missal Diário — Paróquia São Sebastião

Site preparado para funcionar sem atualização manual.

## O que ele faz

- abre automaticamente na data atual (fuso de Brasília);
- contém as marcações de 30/09/2026 a 31/12/2026;
- usa o Missal Romano CNBB 2023 como base das páginas;
- mantém marcações futuras como **sugestão** quando ainda não há folheto oficial;
- verifica automaticamente o site da Arquidiocese de Brasília às 05h, 08h, 11h, 14h, 17h e 20h;
- quando encontra um novo PDF de **O Povo de Deus**, tenta identificar Saudação, Ato Penitencial, página do formulário, Prefácio, Oração Eucarística, aclamação e presença de bênção solene;
- só grava alterações quando encontrou informação nova.

## Publicação

Este projeto foi preparado para GitHub Pages.

1. Crie um repositório público.
2. Envie todos estes arquivos para a branch `main`.
3. Em **Settings → Pages**, selecione **GitHub Actions** como fonte.
4. O workflow `Publicar site no GitHub Pages` publicará o endereço.
5. O workflow `Atualizar folheto O Povo de Deus` fará as verificações automaticamente.

Não é necessária chave de API paga.

## Observação

A leitura automática do folheto usa reconhecimento por texto. Quando o layout do PDF mudar muito, algum item pode continuar marcado como sugestão em vez de ser alterado incorretamente.

## Regra de liberação das datas

- Os dias que já passaram continuam disponíveis para consulta.
- O dia seguinte não aparece antecipadamente.
- À meia-noite, o novo dia ainda permanece bloqueado.
- A rotina automática começa às 05:00 (horário de Brasília).
- Somente depois que essa rotina termina com sucesso, o arquivo `status.js` é atualizado e o novo dia é liberado.
- A seta para a direita fica desativada quando o usuário já está na data mais recente liberada.

## Revisão e correção antes da publicação das 05:00

A rotina das 05:00 não bloqueia mais uma data por causa de inconsistências corrigíveis.

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

## Atualização diária sem datas pré-cadastradas

O site não mantém datas futuras pré-cadastradas. A partir de 30/09/2026, cada novo dia é analisado às 05:00 (horário de Brasília), adicionado ao `data.js` e publicado. Os dias anteriores permanecem como histórico; datas futuras não ficam disponíveis.



## Regra de responsividade

Toda alteração visual, estrutural ou de navegação feita no site deve ser aplicada e conferida também na versão mobile. Nenhuma melhoria deve ser considerada concluída apenas no layout de computador.

Ao alterar o site:
- manter o comportamento e a identidade visual consistentes entre desktop e celular;
- ajustar tamanhos, espaçamentos, quebras de linha, botões, cartões e animações para telas menores;
- verificar se nenhum texto, número, botão ou elemento fica cortado, sobreposto ou fora da tela no mobile;
- preservar boa legibilidade e facilidade de toque no celular.
