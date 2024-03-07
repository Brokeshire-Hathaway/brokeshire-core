import datetime

import pandas as pd
from telethon.sync import TelegramClient

chats = ["https://t.me/c4dotgg"]

# Initialize a list to collect data dictionaries
data_list = []

for chat in chats:
    with TelegramClient(
        "Scrape",
        "23727259",  # type: ignore
        "a9867f805aa7d2ef202bdb90c49bb793",
    ) as client:
        for message in client.iter_messages(
            chat, offset_date=datetime.date.today(), reverse=True
        ):
            print(message)
            data = {
                "group": chat,
                "sender": message.sender_id,
                "text": message.text,
                "date": message.date,
            }

            # Append the data dictionary to the list
            data_list.append(data)

# Create a DataFrame from the list of dictionaries
df = pd.DataFrame(data_list)

df["date"] = df["date"].dt.tz_localize(None)

df.to_csv("./data_{}.csv".format(datetime.date.today()), index=False)
