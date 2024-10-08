STARKNET_GET_BLOCK_WITH_TX_HASHES = {
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "block_hash": "0x3a095054a69b74031cefb69117589868a710c510c2d74e5642890a30f7cb257",
        "block_number": 488504,
        "l1_gas_price": {"price_in_wei": "0x3984d9ad5"},
        "new_root": "0x75baeafd067eee63c55a5731ab0b961248989163089eccddbace60e1246cbb7",
        "parent_hash": "0xfa56fbc13ff0f7217b38406b5218dc658b5a21769f48b48f7126da50aa614d",
        "sequencer_address": "0x1176a1bd84444c89232ec27754698e5d2e7e1a7f1539f12027f28b23ec9f3d8",
        "starknet_version": "0.12.3",
        "status": "ACCEPTED_ON_L2",
        "timestamp": 1703981785,
        "transactions": [
            "0x53e20a450262f2675892b73cb7f7a1b55d9ffb71e14b9f08f1c69f27efc79e0",
            "0x5a8b58688fb5d180084943be4aaefc57ef372fcba78dfa69809f412da3bc2d8",
            "0x64604c7e94928e22adb80c081a780beb7a8a332f6bcea8098b929e9acc44f51",
            "0xac3d42f8ca05a9514836bb1432786442848e5eac7953627c527acf56df4e65",
            "0x638bdf16cdd2b8c506feb966ae0418e72dc92d43fd7cd01d197a6d7cb81c5ef",
            "0x2a835c729294ef157f41876430b251261066db2b68b3f24c0108578d5a28027",
            "0x27284b0c5feb093c9cb2e727c2a1110ec6b48e8bdad8119a868814f73bd2f6a",
        ],
    },
}

STARKNET_GET_BLOCK_WITH_TXS = {
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "block_hash": "0x595bb9a4b6119a43a252c777d7e1598b950a9429e97a06440c79d900fbdd7c7",
        "block_number": 488508,
        "l1_gas_price": {"price_in_wei": "0x3a026e787"},
        "new_root": "0x39437021e3723ccec7eeb038cb611340a4e1621279a3960fb3b0bc1728681cc",
        "parent_hash": "0x7b8e6c28a86c5e694568a6105e7d8e7bc0e6224d94bf4328eeaae37d9769bdb",
        "sequencer_address": "0x1176a1bd84444c89232ec27754698e5d2e7e1a7f1539f12027f28b23ec9f3d8",
        "starknet_version": "0.12.3",
        "status": "ACCEPTED_ON_L2",
        "timestamp": 1703982120,
        "transactions": [
            {
                "calldata": [
                    "0x1",
                    "0x6a05844a03bb9e744479e3298f54705a35966ab04140d3d8dd797c1f6dc49d0",
                    "0x3f01d80498096f7929858b5fc97cdfbd676b5d2ee673407df0c957d6a0fef5f",
                    "0x0",
                    "0x1",
                    "0x1",
                    "0x7300100008000000000000000000000000",
                ],
                "max_fee": "0xa5532fac9391",
                "nonce": "0x11",
                "sender_address": "0x234f0bb15a195899315d0e8054ae10e20eabc8291746ea3de300e1912c037a2",
                "signature": [
                    "0xfcf4d8a9e31bbc669e9b011974721947db41a62c2080839e284103837e3aea",
                    "0xbc82227a425d46f30c153a2d2482bbfd5807ff03861f02f31d2fa685f43b13",
                ],
                "transaction_hash": "0x7438df8cac9c3e61890a5b77e666e030a03788cb78fe58718f69f586d2169cf",
                "type": "INVOKE",
                "version": "0x1",
            },
            {
                "calldata": [
                    "0x2",
                    "0x49d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7",
                    "0x219209e083275171774dab1df80982e9df2096516f06319c5c6d71ae0a8480c",
                    "0x0",
                    "0x3",
                    "0xf6f4cf62e3c010e0ac2451cc7807b5eec19a40b0faacd00cca3914280fdf5a",
                    "0x15543c3708653cda9d418b4ccd3be11368e40636c10c44b18cfe756b6d88b29",
                    "0x3",
                    "0x15",
                    "0x18",
                    "0xf6f4cf62e3c010e0ac2451cc7807b5eec19a40b0faacd00cca3914280fdf5a",
                    "0x4e6216e25201bc",
                    "0x0",
                    "0x49d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7",
                    "0x53c91253bc9682c04929ca02ed00b3e423f6710d2ee7e0d5ebb06f3ecf368a8",
                    "0x4e6216e25201bc",
                    "0x0",
                    "0x304dfd3",
                    "0x0",
                    "0x32e1098e4ecb1c5c7f2a5bdde2ba3d12820cb37e2cf05fe79ad4bfbb058b234",
                    "0x1",
                    "0x49d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7",
                    "0x53c91253bc9682c04929ca02ed00b3e423f6710d2ee7e0d5ebb06f3ecf368a8",
                    "0xf4240",
                    "0x5",
                    "0x5dd3d2f4429af886cd1a3b08289dbcea99a294197e9eb43b0e0325b4b",
                    "0x7",
                    "0x49d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7",
                    "0x53c91253bc9682c04929ca02ed00b3e423f6710d2ee7e0d5ebb06f3ecf368a8",
                    "0x20c49ba5e353f80000000000000000",
                    "0x3e8",
                    "0x0",
                    "0x101f90a10d186cf8be50b33d5ac6",
                    "0x0",
                ],
                "max_fee": "0x1476b081e8000",
                "nonce": "0xf1",
                "sender_address": "0x32e1098e4ecb1c5c7f2a5bdde2ba3d12820cb37e2cf05fe79ad4bfbb058b234",
                "signature": [
                    "0xc98716eea608fd7511c04fd2a2c4d3c147258a3ecff1b6576249e1cb9425d4",
                    "0x22b8f2bd0f2b3263a141b4de7564d9c8cf90c4831828ebd5fcf9f0bf7e6972c",
                ],
                "transaction_hash": "0x1b5afd692f73f4e00bcce3d920f1ad05130e6090cd775b096a012cd2f2a1536",
                "type": "INVOKE",
                "version": "0x1",
            },
            {
                "calldata": [
                    "0x1",
                    "0x6f5e7dbf36fecaf70a74821189176c86a0a121c6827b58df6cf9a0acc1475f7",
                    "0x2f0b3c5710379609eb5495f1ecd348cb28167711b73609fe565a72734550354",
                    "0x3",
                    "0x4704c82a058eef493a6bb17381a2d1f4bcced3bbb766c9826e74769d86975ce",
                    "0x1b52f0",
                    "0x0",
                ],
                "max_fee": "0x83cbf8e6208f",
                "nonce": "0x2d",
                "sender_address": "0x6054b8bc4375bbb94604596629b55895f2a4211852c9275933683f1014cc679",
                "signature": [
                    "0x7a0128594be8b90050fad2beef4f38659fb1857b071cb22c3767e64e9948f7d",
                    "0x6ca5736b00e435e0c550afd6b65abf04ee50dd31dee63db821d4e275a3157b4",
                ],
                "transaction_hash": "0x75358b5ea05367122036da30f2ed4396254370e17a3f5ec905a92d1e399d8e9",
                "type": "INVOKE",
                "version": "0x1",
            },
        ],
    },
}

ZK_SYNC_ERA_BLOCK_WITH_TXS = {
    "hash": "0x196827fc23acf23fe9ca748a5800a9e45b2271ab8588ebfd990ddb3eff2fbfea",
    "parentHash": "0x34d33b84e358565b9372bb5bbaff1974f647c41a6e1462d335d566575d8bfb61",
    "sha3Uncles": "0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347",
    "miner": "0x0000000000000000000000000000000000000000",
    "stateRoot": "0x0000000000000000000000000000000000000000000000000000000000000000",
    "transactionsRoot": "0x0000000000000000000000000000000000000000000000000000000000000000",
    "receiptsRoot": "0x0000000000000000000000000000000000000000000000000000000000000000",
    "number": "0x1312d00",
    "l1BatchNumber": "0x4eddd",
    "gasUsed": "0x3dbb52",
    "gasLimit": "0xffffffff",
    "baseFeePerGas": "0xee6b280",
    "extraData": "0x",
    "logsBloom": "0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "timestamp": "0x6563b016",
    "l1BatchTimestamp": "0x6563afc8",
    "difficulty": "0x0",
    "totalDifficulty": "0x0",
    "sealFields": [],
    "uncles": [],
    "transactions": [
        {
            "hash": "0x6ba38797c514c6df6b07565c78ad7bcab8a002656e1e22549c9ecf8d68132cdf",
            "nonce": "0x1",
            "blockHash": "0x196827fc23acf23fe9ca748a5800a9e45b2271ab8588ebfd990ddb3eff2fbfea",
            "blockNumber": "0x1312d00",
            "transactionIndex": "0x0",
            "from": "0xb8ea6b00128a82ce0c2d54ca2daa1354b52ca1c7",
            "to": "0x493257fd37edb34451f62edf8d2a0c418852ba4c",
            "value": "0x0",
            "gasPrice": "0xee6b280",
            "gas": "0x99206",
            "input": "0x095ea7b30000000000000000000000002da10a1e27bf85cedd8ffb1abbe97e53391c0295ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "v": "0x1",
            "r": "0x6f1994009be99b89aca7b2a6d50487448cdd929f8293e2e641290cf5fc3e1ff0",
            "s": "0x51a21a0a1c72ea25da3f5b81b340f9fb09b4908b83c2ff769cefc7af27581dd",
            "type": "0x2",
            "maxFeePerGas": "0x59682f00",
            "maxPriorityFeePerGas": "0x3b9aca00",
            "chainId": "0x144",
            "l1BatchNumber": "0x4eddd",
            "l1BatchTxIndex": "0x18f",
        },
        {
            "hash": "0xffdb780a3ae00cb1fa2e9fe51b3215553b9db78eebad3b83299769647ad9e7f9",
            "nonce": "0x2d",
            "blockHash": "0x196827fc23acf23fe9ca748a5800a9e45b2271ab8588ebfd990ddb3eff2fbfea",
            "blockNumber": "0x1312d00",
            "transactionIndex": "0x1",
            "from": "0xf2da8978e9372805baa02803ed0c762c9022bbc0",
            "to": "0x85b890cf3a456f505c2932a1e3451035e42dc484",
            "value": "0x0",
            "gasPrice": "0xee6b280",
            "gas": "0x59e7c",
            "input": "0xb23d404c",
            "v": "0x0",
            "r": "0x4e8a2cbc7d584bab67718aa39beda581faef1bdecb7a5f6a110bb0885934af4",
            "s": "0x4821b5bd8c2db27dc2641ebc1cd5a37097e71e54c8f5bf64a68c318bf1d8b828",
            "type": "0x2",
            "maxFeePerGas": "0x77359400",
            "maxPriorityFeePerGas": "0x59682f00",
            "chainId": "0x144",
            "l1BatchNumber": "0x4eddd",
            "l1BatchTxIndex": "0x190",
        },
    ],
    "size": "0x0",
    "mixHash": "0x0000000000000000000000000000000000000000000000000000000000000000",
    "nonce": "0x0000000000000000",
}

STARKNET_TRACE_BLOCK_TRANSACTIONS = {
    "trace_root": {
        "type": "INVOKE",
        "validate_invocation": {
            "contract_address": "0x37bbb23e3414fd67d4eb7cde5dccb4b377fe02d4883b5bc8a8fbab35a81d8e9",
            "entry_point_selector": "0x162da33a4585851fe8d3af3c2a9c60b557814e221e0d4f30ff0b2189d9c7775",
            "calldata": [
                "0x1",
                "0x49d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7",
                "0x83afd3f4caedc6eebf44246fe54e38c95e3179a5ec9ea81740eca5b482d12e",
                "0x0",
                "0x3",
                "0x3",
                "0x7916596feab669322f03b6df4e71f7b158e291fd8d273c0e53759d5b7240b4a",
                "0x116933ea5369f0",
                "0x0",
            ],
            "caller_address": "0x0",
            "class_hash": "0x25ec026985a3bf9d0cc1fe17326b245dfdc3ff89b8fde106542a3ea56c5a918",
            "entry_point_type": "EXTERNAL",
            "call_type": "CALL",
            "result": [],
            "calls": [
                {
                    "contract_address": "0x37bbb23e3414fd67d4eb7cde5dccb4b377fe02d4883b5bc8a8fbab35a81d8e9",
                    "entry_point_selector": "0x162da33a4585851fe8d3af3c2a9c60b557814e221e0d4f30ff0b2189d9c7775",
                    "calldata": [
                        "0x1",
                        "0x49d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7",
                        "0x83afd3f4caedc6eebf44246fe54e38c95e3179a5ec9ea81740eca5b482d12e",
                        "0x0",
                        "0x3",
                        "0x3",
                        "0x7916596feab669322f03b6df4e71f7b158e291fd8d273c0e53759d5b7240b4a",
                        "0x116933ea5369f0",
                        "0x0",
                    ],
                    "caller_address": "0x0",
                    "class_hash": "0x33434ad846cdd5f23eb73ff09fe6fddd568284a0fb7d1be20ee482f044dabe2",
                    "entry_point_type": "EXTERNAL",
                    "call_type": "DELEGATE",
                    "result": [],
                    "calls": [],
                    "events": [],
                    "messages": [],
                    "execution_resources": {
                        "steps": 190,
                        "range_check_builtin_applications": 3,
                        "ecdsa_builtin_applications": 1,
                    },
                }
            ],
            "events": [],
            "messages": [],
            "execution_resources": {
                "steps": 250,
                "range_check_builtin_applications": 3,
                "ecdsa_builtin_applications": 1,
            },
        },
        "execute_invocation": {
            "contract_address": "0x37bbb23e3414fd67d4eb7cde5dccb4b377fe02d4883b5bc8a8fbab35a81d8e9",
            "entry_point_selector": "0x15d40a3d6ca2ac30f4031e42be28da9b056fef9bb7357ac5e85627ee876e5ad",
            "calldata": [
                "0x1",
                "0x49d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7",
                "0x83afd3f4caedc6eebf44246fe54e38c95e3179a5ec9ea81740eca5b482d12e",
                "0x0",
                "0x3",
                "0x3",
                "0x7916596feab669322f03b6df4e71f7b158e291fd8d273c0e53759d5b7240b4a",
                "0x116933ea5369f0",
                "0x0",
            ],
            "caller_address": "0x0",
            "class_hash": "0x25ec026985a3bf9d0cc1fe17326b245dfdc3ff89b8fde106542a3ea56c5a918",
            "entry_point_type": "EXTERNAL",
            "call_type": "CALL",
            "result": ["0x1"],
            "calls": [
                {
                    "contract_address": "0x37bbb23e3414fd67d4eb7cde5dccb4b377fe02d4883b5bc8a8fbab35a81d8e9",
                    "entry_point_selector": "0x15d40a3d6ca2ac30f4031e42be28da9b056fef9bb7357ac5e85627ee876e5ad",
                    "calldata": [
                        "0x1",
                        "0x49d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7",
                        "0x83afd3f4caedc6eebf44246fe54e38c95e3179a5ec9ea81740eca5b482d12e",
                        "0x0",
                        "0x3",
                        "0x3",
                        "0x7916596feab669322f03b6df4e71f7b158e291fd8d273c0e53759d5b7240b4a",
                        "0x116933ea5369f0",
                        "0x0",
                    ],
                    "caller_address": "0x0",
                    "class_hash": "0x33434ad846cdd5f23eb73ff09fe6fddd568284a0fb7d1be20ee482f044dabe2",
                    "entry_point_type": "EXTERNAL",
                    "call_type": "DELEGATE",
                    "result": ["0x1"],
                    "calls": [
                        {
                            "contract_address": "0x49d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7",
                            "entry_point_selector": "0x83afd3f4caedc6eebf44246fe54e38c95e3179a5ec9ea81740eca5b482d12e",
                            "calldata": [
                                "0x7916596feab669322f03b6df4e71f7b158e291fd8d273c0e53759d5b7240b4a",
                                "0x116933ea5369f0",
                                "0x0",
                            ],
                            "caller_address": "0x37bbb23e3414fd67d4eb7cde5dccb4b377fe02d4883b5bc8a8fbab35a81d8e9",
                            "class_hash": "0x5ffbcfeb50d200a0677c48a129a11245a3fc519d1d98d76882d1c9a1b19c6ed",
                            "entry_point_type": "EXTERNAL",
                            "call_type": "CALL",
                            "result": ["0x1"],
                            "calls": [],
                            "events": [
                                {
                                    "order": 0,
                                    "keys": ["0x99cd8bde557814842a3121e8ddfd433a539b8c9f14bf31ebf108d12e6196e9"],
                                    "data": [
                                        "0x37bbb23e3414fd67d4eb7cde5dccb4b377fe02d4883b5bc8a8fbab35a81d8e9",
                                        "0x7916596feab669322f03b6df4e71f7b158e291fd8d273c0e53759d5b7240b4a",
                                        "0x116933ea5369f0",
                                        "0x0",
                                    ],
                                }
                            ],
                            "messages": [],
                            "execution_resources": {
                                "steps": 876,
                                "memory_holes": 56,
                                "pedersen_builtin_applications": 4,
                                "range_check_builtin_applications": 27,
                            },
                        }
                    ],
                    "events": [
                        {
                            "order": 1,
                            "keys": ["0x5ad857f66a5b55f1301ff1ed7e098ac6d4433148f0b72ebc4a2945ab85ad53"],
                            "data": [
                                "0x1dda9f9ab1b8ffd6f45026c8af090eea92abd10430179eba7b9e0c457cb8a9d",
                                "0x1",
                                "0x1",
                            ],
                        }
                    ],
                    "messages": [],
                    "execution_resources": {
                        "steps": 1095,
                        "memory_holes": 59,
                        "pedersen_builtin_applications": 4,
                        "range_check_builtin_applications": 30,
                    },
                }
            ],
            "events": [],
            "messages": [],
            "execution_resources": {
                "steps": 1155,
                "memory_holes": 59,
                "pedersen_builtin_applications": 4,
                "range_check_builtin_applications": 30,
            },
        },
        "fee_transfer_invocation": {
            "contract_address": "0x49d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7",
            "entry_point_selector": "0x83afd3f4caedc6eebf44246fe54e38c95e3179a5ec9ea81740eca5b482d12e",
            "calldata": [
                "0x1176a1bd84444c89232ec27754698e5d2e7e1a7f1539f12027f28b23ec9f3d8",
                "0x33accea23d9e",
                "0x0",
            ],
            "caller_address": "0x37bbb23e3414fd67d4eb7cde5dccb4b377fe02d4883b5bc8a8fbab35a81d8e9",
            "class_hash": "0x5ffbcfeb50d200a0677c48a129a11245a3fc519d1d98d76882d1c9a1b19c6ed",
            "entry_point_type": "EXTERNAL",
            "call_type": "CALL",
            "result": ["0x1"],
            "calls": [],
            "events": [
                {
                    "order": 0,
                    "keys": ["0x99cd8bde557814842a3121e8ddfd433a539b8c9f14bf31ebf108d12e6196e9"],
                    "data": [
                        "0x37bbb23e3414fd67d4eb7cde5dccb4b377fe02d4883b5bc8a8fbab35a81d8e9",
                        "0x1176a1bd84444c89232ec27754698e5d2e7e1a7f1539f12027f28b23ec9f3d8",
                        "0x33accea23d9e",
                        "0x0",
                    ],
                }
            ],
            "messages": [],
            "execution_resources": {
                "steps": 876,
                "memory_holes": 56,
                "pedersen_builtin_applications": 4,
                "range_check_builtin_applications": 27,
            },
        },
        "state_diff": {
            "storage_diffs": [
                {
                    "address": "0x49d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7",
                    "storage_entries": [
                        {
                            "key": "0x69ec6b5d1637dc1f6dd88bea84c9b4213bceae2c6542bf1fdaabe9480e84c4f",
                            "value": "0x339948ddd64c",
                        },
                        {
                            "key": "0x5f8aea6a6c564feabddd8f550373654f27ff38c1b2eeceb72b4c08df2aefd4f",
                            "value": "0x2288aad6073914c",
                        },
                        {
                            "key": "0x5496768776e3db30053404f18067d81a6e06f5a2b0de326e21298fd9d569a9a",
                            "value": "0x125f0da8c89cdbaa21",
                        },
                    ],
                }
            ],
            "nonces": [
                {
                    "contract_address": "0x37bbb23e3414fd67d4eb7cde5dccb4b377fe02d4883b5bc8a8fbab35a81d8e9",
                    "nonce": "0x7",
                }
            ],
            "deployed_contracts": [],
            "deprecated_declared_classes": [],
            "declared_classes": [],
            "replaced_classes": [],
        },
    },
    "transaction_hash": "0x1dda9f9ab1b8ffd6f45026c8af090eea92abd10430179eba7b9e0c457cb8a9d",
}
