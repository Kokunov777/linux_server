# Makefile — РГР: клиент-серверное приложение удалённого выполнения команд
CC      ?= gcc
CFLAGS  ?= -O2 -Wall -Wextra
LDFLAGS ?= -lpthread
SRC      = src/server.c
BIN      = src/server

.PHONY: all clean run test client

all: $(BIN)

$(BIN): $(SRC)
	$(CC) $(CFLAGS) -o $(BIN) $(SRC) $(LDFLAGS)

# Запуск сервера (порт по умолчанию 5555 или PORT=...)
run: $(BIN)
	cd src && ./server $(PORT)

# Запуск графического клиента
client:
	cd src && python3 client_gui.py

# Автотесты протокола
test: $(BIN)
	python3 tests/test_protocol.py

clean:
	rm -f $(BIN) src/*.o src/users.conf src/server.log
	rm -rf src/__pycache__ tests/__pycache__
