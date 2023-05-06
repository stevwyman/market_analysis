from models import Security

all_securities = Security.objects.all()
counter = 0
for index, item in enumerate(all_securities):   # default is zero
    print(index, item)