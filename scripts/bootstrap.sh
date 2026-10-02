VAGRANT_HOME="/home/vagrant"

sudo timedatectl set-timezone America/Recife

sudo apt-get install gnupg

sudo apt-get -y update

sudo apt-get -y install software-properties-common build-essential \
				libpq-dev autoconf unzip pkg-config libssl-dev \
				python3-dev python3-venv graphviz graphviz-dev

# cria o alias no profile
echo " 
alias python=python3" >> $VAGRANT_HOME/.profile
source $VAGRANT_HOME/.profile

# GENERAL CONF
#-------------------------------------------------------------------------------
echo "set nocompatible" > $VAGRANT_HOME/.vimrc
sudo chown vagrant:vagrant $VAGRANT_HOME/.vimrc

# SSH CONF
#-------------------------------------------------------------------------------
# copy ssh config
cp /vagrant/resources/ssh/config $VAGRANT_HOME/.ssh
sudo chown -R vagrant:vagrant $VAGRANT_HOME/.ssh/config

# cria o ambiente virtual venv
python3 -m venv $VAGRANT_HOME/venv 


# configura o bash para ativar o ambiente virtual no login / ssh
echo " 

source venv/bin/activate
cd /vagrant/web-folder/pws
python -m debugpy --listen 0.0.0.0:8001 --wait-for-client manage.py runserver 0:8000
" >> $VAGRANT_HOME/.bashrc

# ativa o ambiente virtual na sessão vagrant provission (instalação)
source $VAGRANT_HOME/venv/bin/activate

# instala o debugger
python3 -m pip install --upgrade debugpy

pip install wheel
pip install -r /vagrant/resources/requirements.txt

# BASH CONF
#-------------------------------------------------------------------------------
# altera o template settings ALLOWED_HOSTS = ['192.168.100.120', 'localhost', '127.0.0.1']
cp /vagrant/resources/django/settings.py-tpl $VAGRANT_HOME/venv/lib/python3.8/site-packages/django/conf/project_template/project_name/
