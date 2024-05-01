import re

from load_networks.listofchains import chains


def create_cypher_strings(chains):
    result = []  # Initialize an empty list to store the result

    for chain in chains:
        oldname = chain["name"]
        name = re.sub(r"\s", "", oldname)
        native_coin_id = chain["native_coin_id"]
        # Ensure 'name' and 'native_coin_id' exist
        cypher_string = f"CREATE ({name}:Chain {{name: '{name}', native_coin_id: '{native_coin_id}'}})"
        result.append(cypher_string)
        print(f"result: {result}")
    return result


networks = create_cypher_strings(chains)

with open("cypher_to_load_networks.txt", "w") as f:
    f.write("\n".join(networks))
print("Cypher strings written to cypher.txt successfully!")
