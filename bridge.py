from web3 import Web3
from web3.providers.rpc import HTTPProvider
from web3.middleware import ExtraDataToPOAMiddleware  # Necessary for POA chains
from datetime import datetime
import json
import pandas as pd


def connect_to(chain):
    if chain == 'source':  # The source contract chain is avax
        api_url = "https://api.avax-test.network/ext/bc/C/rpc"

    if chain == 'destination':  # The destination contract chain is bsc
        api_url = "https://data-seed-prebsc-1-s1.binance.org:8545/"

    if chain in ['source', 'destination']:
        w3 = Web3(Web3.HTTPProvider(api_url))
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        return w3

    return None


def get_contract_info(chain, contract_info):

    try:
        with open(contract_info, 'r') as f:
            contracts = json.load(f)
    except Exception as e:
        print(f"Failed to read contract info\nPlease contact your instructor\n{e}")
        return 0

    return contracts[chain]


def scan_blocks(chain, contract_info="contract_info.json"):


    if chain not in ['source', 'destination']:
        print(f"Invalid chain: {chain}")
        return 0

    w3 = connect_to(chain)
    if w3 is None:
        return 0

    info = get_contract_info(chain, contract_info)
    if info == 0:
        return 0

    contract_address = Web3.to_checksum_address(info["address"])
    abi = info["abi"]
    contract = w3.eth.contract(address=contract_address, abi=abi)

    latest_block = w3.eth.block_number
    start_block = max(0, latest_block - 50)
    end_block = latest_block

    acct = w3.eth.account.from_key(info["private_key"])
    nonce = w3.eth.get_transaction_count(acct.address)

    if chain == "source":
        event_filter = contract.events.Deposit.create_filter(
            from_block=start_block,
            to_block=end_block
        )
        events = event_filter.get_all_entries()

        dest_info = get_contract_info("destination", contract_info)
        dest_w3 = connect_to("destination")
        dest_contract = dest_w3.eth.contract(
            address=Web3.to_checksum_address(dest_info["address"]),
            abi=dest_info["abi"]
        )
        dest_acct = dest_w3.eth.account.from_key(dest_info["private_key"])
        dest_nonce = dest_w3.eth.get_transaction_count(dest_acct.address)

        for evt in events:
            token = evt["args"]["token"]
            recipient = evt["args"]["recipient"]
            amount = evt["args"]["amount"]

            dest_nonce = dest_w3.eth.get_transaction_count(dest_acct.address)

            tx = dest_contract.functions.wrap(
                token,
                recipient,
                amount
            ).build_transaction({
                "from": dest_acct.address,
                "nonce": dest_nonce,
                "gas": 500000,
                "gasPrice": dest_w3.eth.gas_price,
                "chainId": dest_w3.eth.chain_id
            })

            signed_tx = dest_w3.eth.account.sign_transaction(
                tx,
                private_key=dest_info["private_key"]
            )
            tx_hash = dest_w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            print(dest_w3.to_hex(tx_hash))
            dest_w3.eth.wait_for_transaction_receipt(tx_hash)

    elif chain == "destination":
        event_filter = contract.events.Unwrap.create_filter(
            from_block=start_block,
            to_block=end_block
        )
        events = event_filter.get_all_entries()

        source_info = get_contract_info("source", contract_info)
        source_w3 = connect_to("source")
        source_contract = source_w3.eth.contract(
            address=Web3.to_checksum_address(source_info["address"]),
            abi=source_info["abi"]
        )
        source_acct = source_w3.eth.account.from_key(source_info["private_key"])
        source_nonce = source_w3.eth.get_transaction_count(source_acct.address)

        for evt in events:
            token = evt["args"]["underlying_token"]
            recipient = evt["args"]["to"]
            amount = evt["args"]["amount"]

            source_nonce = source_w3.eth.get_transaction_count(source_acct.address)

            tx = source_contract.functions.withdraw(
                token,
                recipient,
                amount
            ).build_transaction({
                "from": source_acct.address,
                "nonce": source_nonce,
                "gas": 500000,
                "gasPrice": source_w3.eth.gas_price,
                "chainId": source_w3.eth.chain_id
            })

            signed_tx = source_w3.eth.account.sign_transaction(
                tx,
                private_key=source_info["private_key"]
            )
            tx_hash = source_w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            print(source_w3.to_hex(tx_hash))
            source_w3.eth.wait_for_transaction_receipt(tx_hash)

    return 1
