# Auditoria técnica do AeroFox 1.1.1

O log do AeroFox 1.1.0 registrou uma resposta offline após 15,2 s em uma conversa sobre um traje EVA. A versão antiga usava o mesmo aviso para finalização por limite de geração, texto vazio e divergência do alias. O log daquela versão não registrava qual dessas condições ocorreu. A inspeção confirmou que qualquer resposta com finish_reason diferente de stop era descartada, embora o servidor pudesse ter gerado uma parte útil antes de atingir o limite.

A versão 1.1.1 registra a etapa, o motivo de finalização, a contagem de tokens e a duração. Um plano completo continua válido mesmo quando termina no limite. Se o plano ficar incompleto e houver uma ferramenta local aplicável, o agente pode executar a análise e tentar sintetizar a resposta. Se o texto terminar no limite, a aplicação preserva as frases completas e verificáveis. Quando a síntese falha, a resposta de contingência usa o resultado científico já produzido. Fila ocupada, timeout e indisponibilidade aparecem com avisos distintos.

## Achados e correções

| Área | Problema constatado | Mudança |
| --- | --- | --- |
| Interpretação | Na versão anterior, perguntas sobre fiação e oxigênio de um traje acionaram ferramentas de combustão de gotas do FLEX. | Ferramentas compatíveis com o domínio do traje têm precedência. Pedidos de dados do FLEX continuam acessíveis quando explícitos. |
| Estado | A leitura de pressão negativa podia reconhecer apenas o valor positivo. Uma pergunta hipotética podia sobrescrever os parâmetros do projeto. | Sinal e faixa da pressão são validados. Hipóteses ficam restritas ao turno. Uma preferência de idioma expressa persiste na conversa. |
| Dados | A busca de um número FLEX diferente de FLEX-035 podia retornar resultados agregados de outros ensaios. | A consulta usa a chave oficial vinculada pelo identificador CIR. Um número ausente retorna a lacuna do snapshot. |
| Respostas | A síntese podia diluir a conclusão em um parágrafo longo. Os números medidos ficavam recolhidos. | A instrução começa pela resposta direta. O renderer preserva parágrafos e listas. Os resultados quantitativos relevantes ficam visíveis junto à interpretação e à figura. |
| Segurança | As buscas de material permitiam que um nome fosse interpretado como expressão regular. O CSV podia carregar conteúdo interpretável como fórmula. | Os nomes são limitados e tratados literalmente. Campos textuais perigosos do CSV são neutralizados, preservando valores numéricos. A API limita escritas, rejeita origem cruzada fora da configuração aprovada e deixa de registrar identificadores de sessão nas rotas. |
| Operação | A perda da explicação derrubava toda a ferramenta para o caminho offline. | Separação entre plano, execução e síntese. Recuperações usam orçamento limitado. A API e os logs deixam visível a etapa que falhou. |
| Visualização | O chat exibia medidas e matrizes, mas não tinha fluxograma com ramificações. Um erro assíncrono no Plotly podia ficar sem retorno na interface. | Fluxograma por sistema com decisões e fontes, exportação Mermaid e retorno com CSV quando um gráfico falha. |

## Limites da revisão

A triagem de incêndio e os fluxogramas apoiam o planejamento de ensaios. As recomendações devem ser conferidas para o material, a atmosfera e a montagem representados. O modelo de linguagem ainda pode equivocar-se em uma interpretação qualitativa. O limite da fila permanece, e uma interrupção real do processo de inferência usa o modo offline até o runtime voltar.

A instância revisada foi iniciada em http://127.0.0.1:8001/ com o mesmo modelo local. A versão que já estava em 8000 permite consultar as conversas anteriores enquanto o processo continua ativo. Cada instância mantém suas próprias sessões em memória.

Consulte [as visualizações e a reprodução em Python/Colab](VISUALIZATIONS.md).


## Verificação executada

- A suíte local passou em 59 testes. Os testes de regressão injetam tanto um plano interrompido quanto texto cortado com uma frase completa, e conferem se o gráfico já calculado sobrevive.
- Qwen3-4B executou 7 de 7 casos no benchmark de integração. A mediana foi 9,08 s nesta rodada. Uma segunda sequência de 5 turnos sobre traje EVA manteve o modelo ativo. Ela cobriu o primeiro controle recomendado, camadas internas, falha de fiação, oxigênio e um fluxograma como continuação.
- Em chamada direta ao servidor, um limite forçado de 8 tokens produziu finish_reason=length. Isso comprova que o servidor reporta o limite separadamente. A causa exata do evento histórico de 15,2 s continua indeterminada.
- Chromium verificou as matrizes Lua e Marte no mesmo chat, o CSV, o gráfico medido e um fluxograma em português no celular. O arquivo .mmd baixado trouxe as ramificações do mesmo resultado Python.
- A revisão manual dos textos da sequência EVA encontrou recomendações ainda genéricas para camadas internas. As fontes atuais ajudam a definir os ensaios e suas condições. Uma comparação de candidatos precisa informar a camada, o conjunto instalado e os resultados do ensaio comparável.

Resultados do modelo em reports/reliability_111_live.json e reports/reliability_111_eva.json. O fluxo de exportação Mermaid foi verificado localmente. O exemplo reutilizável foi documentado para Colab, onde a execução remota ainda não foi repetida.
