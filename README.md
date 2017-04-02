# MITM Postman

A tool that creates a Postman collection from App / Web API calls

# Setup

Install mitm proxy

```sh
pip3 install mitmproxy
```

Clone mitm_postman

```sh
git clone https://github.com/viraja1/mitm_postman.git
```

```sh
cd mitm_postman
```

Run the command to start the proxy server and create the postman collection for the APIs calls from the client to a particular domain

```sh
./mitm "example.com" "collection_name"
```

Configure the proxy settings on the client (port 9500)

