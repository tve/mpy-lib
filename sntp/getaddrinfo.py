import socket

print("\ntest getaddrinfo of non-existant hostname")
try:
    res = socket.getaddrinfo('nonexistant.example.com', 80)
    print("getaddrinfo returned", res)
except Exception as e:
    print("getaddrinfo raised", e)

print("\ntest getaddrinfo of empty hostname")
try:
    res = socket.getaddrinfo('', 80)
    print("getaddrinfo returned", res)
except Exception as e:
    print("getaddrinfo raised", e)

print("\ntest getaddrinfo of bogus hostname")
try:
    res = socket.getaddrinfo('..', 80)
    print("getaddrinfo returned", res)
except Exception as e:
    print("getaddrinfo raised", e)

print("\ntest getaddrinfo of ip address")
try:
    res = socket.getaddrinfo('10.10.10.10', 80)
    print("getaddrinfo returned", len(res), "resolutions")
except Exception as e:
    print("getaddrinfo raised", e)

print("\ntest getaddrinfo of valid hostname")
try:
    res = socket.getaddrinfo('micropython.org', 80)
    print("getaddrinfo returned", len(res), "resolutions")
except Exception as e:
    print("getaddrinfo raised", e)

print("\ntest connecting to hostname")
s = socket.socket()
try:
    s.connect(('micropython.org', 80))
    print("connect actually connected")
except Exception as e:
    print("connect raised", e)
