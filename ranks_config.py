RANKS = [
    {"rank": "Мутант", "min_rating": 300},
    {"rank": "Псих", "min_rating": 250},
    {"rank": "Задрот", "min_rating": 200},
    {"rank": "Умник", "min_rating": 150},
    {"rank": "Школьник", "min_rating": 100},
    {"rank": "Карапуз", "min_rating": 50},
    {"rank": "Амёба", "min_rating": 0}
]

def get_rank_by_rating(rating):
    for rank_info in RANKS:
        if rating >= rank_info["min_rating"]:
            return rank_info["rank"]
    return "Амёба"
