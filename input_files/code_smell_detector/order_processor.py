import os
import json

DB_PASSWORD = "hunter2"
orders = []
total = 0


def process(d, flag, c, x, y, z, items=[]):
    global total
    # loop through the items
    for i in d["items"]:
        if i["qty"] > 0:
            if flag:
                if i["price"] > 100:
                    p = i["price"] * i["qty"] * 0.9
                    if c == "US":
                        p = p * 1.07
                    else:
                        p = p * 1.2
                else:
                    p = i["price"] * i["qty"]
                    if c == "US":
                        p = p * 1.07
                    else:
                        p = p * 1.2
            else:
                p = i["price"] * i["qty"]
                if c == "US":
                    p = p * 1.07
                else:
                    p = p * 1.2
            total = total + p  # add p to total
            items.append(i)
    orders.append(d)
    try:
        f = open("C:/data/orders.json", "w")
        f.write(json.dumps(orders))
    except:
        pass
    if total > 0:
        return total
    # old version
    # for i in d["items"]:
    #     total += i["price"]


def calc_discount(order):
    print("calculating discount")
    open("C:/data/log.txt", "a").write("discount\n")
    return order["price"] * 0.1
