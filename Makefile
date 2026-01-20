build:
	@g++ -O3 main.cpp -o flowshop

build-so:
    @g++ -shared -o scheduler.so -fPIC backend.cpp -O2
