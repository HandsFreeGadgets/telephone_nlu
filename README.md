# Summary

This project provides a German telephone assistant using [Rasa](https://rasa.com) as NLU (natural language understanding) engine.

# Funding

The project was funded by the German Federal Ministry of Education and Research under grant number 01IS22S34 from September 2022 to February 2023. The authors are responsible for the content of this publication.

<img src="BMBF_gefoerdert_2017_en.jpg" width="300px"/>

# Installation

The installation assumes an Ubuntu environment and needs adjustments when using a different distribution.

## Prerequisites

### Python

Install Python 3.8 (should be the default in Ubuntu 20.04):

~~~shell
sudo apt install python3.8
~~~

## Program

Install the program:

~~~shell
pip install git+https://github.com/kaoh/TelephoneNLU.git
~~~

### Install Atom based Processors (Rock Pi X / MeLe Quieter2Q)

~~~shell
pip install git+https://github.com/kaoh/TelephoneNLU.git
pip install --force-reinstall https://github.com/HandsFreeGadgets/python-wheels/releases/download/v0.1/tensorflow-2.8.4-cp38-cp38-linux_x86_64.whl
~~~

## SIP Client Installation

For the telephone functionality a SIP system service is used. 

### Add User to the System

~~~shell
adduser --shell=/bin/false --gecos "Hands-Free User" --disabled-login hands-free-user || true
usermod -a -G audio hands-free-user 
~~~

### Install baresip

Install [baresip](https://github.com/baresip/baresip). This must be compiled manually, but runs both under x86 and aarch64.

#### Prerequisites

~~~shell
sudo apt-get install openssl cmake gcc make
~~~

#### Compilation + Installation

Copy and paste all lines to a shell:

~~~shell
mkdir -p baresip && cd baresip

wget https://github.com/baresip/re/archive/refs/tags/v2.11.0.tar.gz -O re.tgz && mkdir -p re && tar xf re.tgz -C re --strip-components 1
cd re && cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j && cd ..

wget https://github.com/baresip/rem/archive/refs/tags/v2.11.0.tar.gz -O rem.tgz && mkdir -p rem && tar xf rem.tgz -C rem --strip-components 1
cd rem && cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j && cd ..

wget https://github.com/baresip/baresip/archive/refs/tags/v2.11.0.tar.gz -O baresip.tgz && mkdir -p baresip && tar xf baresip.tgz -C baresip --strip-components 1 
cd baresip && cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j && cd ..

sudo sh -c 'cd re && cd build && make install && ldconfig && cd ../.. &&cd rem && cd build && make install && ldconfig && cd ../.. && cd baresip && cd build && make install && ldconfig && cd ../..'
~~~

Take the most recent versions of all dependencies and check if the installation steps are still up-to-date.

#### Configuration baresip

Configure the SIP account. Add to the system's user directory:

~~~shell
sudo mkdir -p /home/hands-free-user/.baresip
sudo nano /home/hands-free-user/.baresip/accounts
sudo chown -R hands-free-user:hands-free-user /home/hands-free-user/.baresip
~~~

__NOTE:__ When testing it locally also create the local user file `~/.baresip/accounts`.

When configuring sipgate insert this content with your username and password:

~~~
<sip:username@sipgate.de>;auth_pass=password;auth_user=username;transport=tcp;sip_autoanswer=yes;answermode=auto;outbound="sip:sip.sipgate.de:5060;transport=tcp"
~~~

#### Systemd Start Up Script

~~~shell
sudo cp baresip.service /lib/systemd/system/
sudo systemctl daemon-reload
systemctl enable baresip.service
systemctl start baresip.service
~~~

##### Check Log

~~~shell
journalctl -u baresip.service
~~~

##### Check baresip Screen Session

~~~shell
screen -ls
screen -R <id>
~~~

## Run as System Service

To run the program at system start execute the following scripts or adjust them to support your OS. 

~~~shell
sudo -i
# execute the following scripts
exit
~~~

Create dedicated system user:

~~~shell
adduser --shell=/bin/false --gecos "Hands-Free User" --disabled-login handsfree
usermod -a -G audio handsfree
~~~

Create Systemd scripts:

~~~shell
mkdir -p /lib/systemd/system/
cp telephone_nlu_actions /lib/systemd/system/
cp telephone_nlu /lib/systemd/system/
~~~

Enable and restart services:

~~~shell
/bin/systemctl enable telephone_nlu_actions
/bin/systemctl restart telephone_nlu_actions
/bin/systemctl enable telephone_nlu
/bin/systemctl restart telephone_nlu
~~~

In case of instabilities a Cron job can be created to restart the server every day:

~~~shell
mkdir -p /etc/cron.d
cat <<EOT > /etc/cron.d/hands_free_telephone
30 3 * * * root /bin/systemctl restart telephone_nlu_actions
30 3 * * * root /bin/systemctl restart telephone_nlu
EOT
~~~

# Execution

Start in one shell the action server:

~~~shell
telephone_nlu_actions
~~~

Start the NLU server:

~~~shell
telephone_nlu
~~~

# Development

## Build Project

Checkout the project:

~~~shell
git clone <URL>
git pull --recurse-submodules
git submodule init
git submodule update
~~~

Install `pyenv` and Python 3.8:

~~~shell
git clone https://github.com/pyenv/pyenv.git ~/.pyenv
# Follow instructions on https://github.com/pyenv/pyenv
sudo apt-get install libbz2-dev libssl-dev libreadline-dev libsqlite3-dev libffi-dev
ldconfig
pyenv install 3.8.16
pyenv local 3.8.16
python3 -m venv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt
~~~

## Test Packaging

Test the `pyproject.toml` package:

~~~shell
python3 -m venv testbuild
source testbuild/bin/activate
pip install -U pip
pip install .
~~~

## Rasa Debug Output

Start Rasa with debug output:

~~~shell
source venv/bin/activate
# Only need on Raspberry Pi / aarch64
export LD_PRELOAD=</usr | <virtual env directory>>/lib/python3.8/site-packages/sklearn/__check_build/../../scikit_learn.libs/libgomp-d22c30c5.so.1.0.0
cd telephone_nlu
rasa run --enable-api -v --debug -m models
~~~

## Train Model

Train the model (execute this only on an x86 environment, not a Raspberry Pi (slow)):

~~~shell
source venv/bin/activate
cd telephone_nlu
rasa train
~~~
    
Test the model:

~~~shell
source venv/bin/activate
cd telephone_nlu
rasa test -s tests
~~~

Try the model:

~~~shell
source venv/bin/activate
# Only need on Raspberry Pi / aarch64
export LD_PRELOAD=</usr | <virtual env directory>>/lib/python3.8/site-packages/sklearn/__check_build/../../scikit_learn.libs/libgomp-d22c30c5.so.1.0.0
cd telephone_nlu
rasa shell --debug
~~~
