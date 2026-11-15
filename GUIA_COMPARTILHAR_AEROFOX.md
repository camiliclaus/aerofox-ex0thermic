# AeroFox 1.1.1 — guia para a equipe

## Baixar e compartilhar

Envie o arquivo **AeroFox_Equipe_v1.1.1.zip** e, se quiser conferir a integridade, o arquivo **AeroFox_Equipe_v1.1.1.zip.sha256**. Este guia também está dentro do ZIP. Extraia a pasta inteira para um caminho curto, por exemplo `C:\Projetos` ou uma pasta direto em Downloads. Isso evita o limite de comprimento de caminhos do Windows nos arquivos de dados da NASA. A pasta contém o aplicativo, a base de dados necessária, o instalador do modelo, os testes e o notebook.

No PowerShell, junto ao ZIP, confira o hash com:

```powershell
Get-FileHash .\AeroFox_Equipe_v1.1.1.zip -Algorithm SHA256
Get-Content .\AeroFox_Equipe_v1.1.1.zip.sha256
```

Os dois valores devem ser iguais, independentemente de maiúsculas e minúsculas.

## Rodar no Windows

1. Instale [Python 3.11 ou 3.12, versão de 64 bits](https://www.python.org/downloads/windows/). Se o instalador oferecer a opção de adicionar Python ao PATH, marque-a.
2. Na pasta extraída `aerofox`, dê dois cliques em `START_AEROFOX.bat`. A primeira execução precisa de internet para instalar os pacotes Python, baixar o llama.cpp e baixar os pesos oficiais. O instalador verifica os hashes dos arquivos de inferência. Não é necessária uma conta do Hugging Face ou uma chave de API.
3. Mantenha a janela do terminal aberta. O navegador será aberto na porta disponível informada no terminal, normalmente [127.0.0.1:8000](http://127.0.0.1:8000/). Confira **Local model ready** na barra lateral. Teste com “Mostre um fluxograma de verificação contra incêndio para um traje EVA”. A resposta deve apresentar o nome do modelo local e um link para exportar o fluxograma em Mermaid.

O modo automático seleciona o Qwen3-4B em uma NVIDIA compatível. Em um computador sem essa GPU, ou se a inicialização da GPU falhar, execute da raiz do projeto:

```powershell
.\START_AEROFOX.bat --model-profile cpu
```

| Perfil | Pesos | Download aproximado dos pesos |
| --- | --- | --- |
| GPU | Qwen3-4B Q4_K_M | 2,50 GB |
| CPU | Qwen2.5-1.5B-Instruct Q4_K_M | 1,12 GB |

A janela do terminal informa o endereço e o perfil usado. O cache padrão fica em `.models/`. Se já tiver o GGUF oficial, coloque o arquivo com seu nome original nessa pasta. O instalador vai verificar o hash e baixar o runtime quando necessário. Os links e hashes dos dois perfis estão em [scripts/local_model.py](scripts/local_model.py).

Para macOS ou Linux, consulte [docs/MODEL_RUNTIME.md](docs/MODEL_RUNTIME.md). O procedimento usa um llama.cpp compatível e `sh ./start_aerofox.sh --external-local-model`.

## Publicar o projeto no GitHub

Uma pessoa da equipe cria um repositório GitHub vazio, por exemplo `aerofox`, e convida os colegas em **Settings → Collaborators**. Escolham a visibilidade do repositório. Para publicação aberta, mantenham o crédito da NASA e consultem as condições de cada fonte em [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

Instale [Git](https://git-scm.com/download/win) e abra um PowerShell dentro da pasta extraída `aerofox`. Nos comandos abaixo, substitua `SUA-EQUIPE` pelo usuário ou organização que criou o repositório:

```powershell
git init -b main
git add .
git status --short
git commit -m "Adiciona AeroFox 1.1.1"
git remote add origin https://github.com/SUA-EQUIPE/aerofox.git
git push -u origin main
```

Antes do commit, confira a lista exibida por `git status --short`. Devem estar lá `backend/`, `frontend/`, `data/`, `docs/`, `notebooks/`, `reports/`, `tests/`, `scripts/`, o instalador, os requisitos, a licença e os arquivos de configuração de exemplo. O `.gitignore` exclui a pasta do modelo, os pesos GGUF, os ambientes virtuais, o arquivo `.env` e os logs. O arquivo `.gitattributes` preserva os bytes originais dos arquivos NASA que o projeto verifica por hash.

Se o repositório da equipe já tiver código, clone-o, crie uma branch, aplique as alterações e envie um pull request. Assim o histórico anterior fica disponível. [Instruções oficiais para enviar código local ao GitHub](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)

Depois do primeiro envio, cada colega pode rodar:

```powershell
git clone https://github.com/SUA-EQUIPE/aerofox.git
cd aerofox
.\START_AEROFOX.bat
```

Para oferecer um download pronto no GitHub, crie a release `v1.1.1` e anexe o ZIP e o arquivo SHA-256. O GitHub hospeda os arquivos para download. A inferência roda na máquina de quem inicia o AeroFox. [Como usar GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)

## Se a equipe quiser hospedar também os pesos

A instalação padrão usa os downloads oficiais do Hugging Face, identificados por revisão e hash. Para fazer um espelho, preserve o arquivo original, a licença Apache-2.0 e a atribuição ao projeto Qwen.

- **CPU:** o GGUF de aproximadamente 1,12 GB pode ser anexado como arquivo de uma GitHub Release. Cada asset precisa ter menos de 2 GiB. [Pesos oficiais para CPU](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/tree/91cad51170dc346986eccefdc2dd33a9da36ead9)
- **GPU:** o GGUF de aproximadamente 2,50 GB supera o limite por arquivo de uma Release e o do Git LFS no plano Free. Um plano com limite maior, como GitHub Team, comporta esse tamanho via Git LFS, sujeito às cotas do plano. O Git comum bloqueia arquivos acima de 100 MiB. [Pesos oficiais para GPU](https://huggingface.co/Qwen/Qwen3-4B-GGUF/tree/bc640142c66e1fdd12af0bd68f40445458f3869b) · [Limites do GitHub](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github) · [Limites do Git LFS](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage)

Se usarem Git LFS para manter um espelho, coloquem os pesos num repositório separado e executem `git lfs install` e `git lfs track "*.gguf"` antes de adicionar os arquivos. No repositório do aplicativo, continuem usando o instalador e os hashes publicados. Um colega pode baixar os pesos do espelho e colocá-los em `.models/` com o nome original. [Configuração oficial do Git LFS](https://docs.github.com/en/repositories/working-with-files/managing-large-files/configuring-git-large-file-storage)

## Onde mexer e como conferir

- **Comportamento e ferramentas:** `backend/aerofox/agent/`, `backend/aerofox/science/` e [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
- **Interface e figuras:** `frontend/` e [docs/VISUALIZATIONS.md](docs/VISUALIZATIONS.md).
- **Modelo e runtime:** `scripts/local_model.py`, [docs/MODEL_RUNTIME.md](docs/MODEL_RUNTIME.md).
- **Base científica e relatório:** `data/`, `notebooks/AeroFox_Comprehensive_Data_Analysis.ipynb` e `docs/`. O relatório PDF e Word descreve a migração 1.1.0. A [auditoria 1.1.1](docs/AUDITORIA_1.1.1.md) documenta as alterações posteriores.

Depois de rodar o instalador uma vez, a equipe pode usar o mesmo ambiente virtual para testar:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

