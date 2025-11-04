def calculate_formula(incisors_mm, formula_name, gender="Male"):
    s = sum(incisors_mm)
    if formula_name == "Tanaka–Johnston":
        return round(((s / 2.0) + 11.0) * 2.0, 2)
    elif formula_name == "Moyers":
        predicted_key = round(10.5 + (s / 2.0), 1)
        table = {
            "male": {
                19.5: 20.44, 20.0: 20.77, 20.5: 21.11, 21.0: 21.44, 21.5: 21.78,
                22.0: 22.11, 22.5: 22.44, 23.0: 22.78, 23.5: 23.11, 24.0: 23.45,
                24.5: 23.78, 25.0: 24.12, 25.5: 24.45
            },
            "female": {
                19.5: 20.39, 20.0: 20.72, 20.5: 21.05, 21.0: 21.37, 21.5: 21.70,
                22.0: 22.02, 22.5: 22.35, 23.0: 22.68, 23.5: 23.00, 24.0: 23.33,
                24.5: 23.65, 25.0: 23.98, 25.5: 24.31
            }
        }
        g = table.get(gender.lower(), table["male"])
        ck = min(g.keys(), key=lambda k: abs(predicted_key - k))
        predicted_value = g[ck]
        return round(predicted_value, 2)
    else:
        return None
    

def calculate_discrepancy(lengths_mm, formula, gender):
    if len(lengths_mm) < 7:
        return None, "⚠️ Need 7 lines: 0=scale, 1=left, 2–5=incisors, 6=right."
    incisors_mm = lengths_mm[2:6]
    predicted = calculate_formula(incisors_mm, formula, gender)
    if predicted is None:
        return None, "⚠️ Invalid formula."
    left = lengths_mm[1]
    right = lengths_mm[6]
    left_space = left - predicted
    right_space = right - predicted
    disc = (left_space + right_space) / 2.0
    return {
        "predicted_mm_per_side": round(predicted, 2),
        "left_space_mm": round(left_space, 2),
        "right_space_mm": round(right_space, 2),
        "discrepancy_mm": round(disc, 2)
    }, "✅ Discrepancy calculated"
    

