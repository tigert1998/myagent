FROM ubuntu:24.04

RUN apt update && apt upgrade -y && apt install -y \
    vim curl language-pack-zh-hans git g++

RUN printf "export LANG=zh_CN.UTF-8\nexport LANGUAGE=zh_CN:zh\n" >> /etc/profile

SHELL ["/bin/bash", "-c"]

RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash && \
    \. "$HOME/.nvm/nvm.sh" && nvm install 24

RUN cd /root && git clone https://github.com/tigert1998/myagent.git && \
    cd /root/myagent && "$HOME/.local/bin/uv" sync