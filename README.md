# teraz
AIを使った便利な総合的なルール群

## Initial Environment Setup (macOS)

The following steps prepare a Mac that does not have Git or Python installed.

1. **Install pyenv**
   Install `pyenv` with Homebrew:
   ```bash
   brew install pyenv
   ```

2. **Install Python 3.13 with pyenv**
   ```bash
   pyenv install 3.13.5
   pyenv global 3.13.5
   ```
   This also installs `pip`.

3. **Verify the installation**
   ```bash
   python3 --version
   pip3 --version
   ```

Once these tools are installed, proceed to the Setup section below.

## Setup

1. **Install Python 3.13.5**
   Ensure Python and `pip` are available on your system.
2. **Clone this repository**
   Run the following command:
   ```bash
   git clone git@github.com:valencia-jp/AI-tools.git
   ```
3. **Navigate into the project directory**
   ```bash
   cd AI-tools/AI-tools
   ```
4. **Create a virtual environment**
   ```bash
   python3 -m venv .venv
   ```
5. **Activate the virtual environment**
   ```bash
   source .venv/bin/activate
   ```
6. **Upgrade pip**
   ```bash
   pip install --upgrade pip
   ```
7. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
8. **Set environment variables**
   The translation feature uses the OpenAI Agents SDK, which requires an OpenAI API key. Set it as `OPENAI_API_KEY`:
   ```bash
   export OPENAI_API_KEY=your-api-key
   ```
9. **Run the application**
   Execute the package as a module so that relative imports work correctly.
   ```bash
   python3 -m app
   ```
   The server runs on 
   `http://127.0.0.1:5050`
   `http://172.16.1.83:5050`
   by default.
