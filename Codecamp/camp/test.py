def update_num(n: list[int]) -> None:
    n.append(y)

x = [1]
y = 2
r = 1
while r <= 10:
    update_num(x)
    r +=1
    y *=2
print(x)