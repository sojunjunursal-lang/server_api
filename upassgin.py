import random
import re

try:
    from faker import Faker
except ImportError:
    print("[!] Faker not installed. Run: pip install Faker")
    exit(1)

fake = Faker()

# Chance a combo gets a numeric suffix (matches the "85% Pure / 15% Numbered" header)
NUMBERED_CHANCE = 0.15

# Signs/separators placed BEFORE the number
SEPARATORS = ["_", "-", ".", "@", "#", "!", "$", "+", ""]


def generate_upass():
    print("=" * 40)
    print("🔥 PURE-DOMINANT U:PASS GENERATOR")
    print("=" * 40)

    try:
        count = int(input("[?] How many upass combos to generate? : ").strip())
        if count <= 0:
            print("[!] Please enter a positive number.")
            return
    except ValueError:
        print("[!] Invalid input. Enter a number.")
        return

    output_file = "upass_extracted.txt"
    generated_set = set()
    attempts = 0
    max_attempts = max(count * 50, 1000)  # safety net against infinite loops

    print(f"\n[*] Spinning up {count} unique combos (85% Pure / 15% Numbered)...")

    with open(output_file, "w", encoding="utf-8") as f:
        while len(generated_set) < count:
            attempts += 1
            if attempts > max_attempts:
                print(f"[!] Safety stop: could only make {len(generated_set)} unique combos.")
                break

            # Clean first name -> strict A-Z / 0-9
            name = re.sub(r'[^a-zA-Z0-9]', '', fake.first_name())
            if not name:
                continue

            # Build optional numeric suffix with a random separator
            suffix = ""
            if random.random() < NUMBERED_CHANCE:
                sep = random.choice(SEPARATORS)          # _ - . @ # ! $ + or nothing
                length = random.randint(1, 4)            # 1–4 digits, not just 3
                num = str(random.randint(10 ** (length - 1), 10 ** length - 1))
                suffix = f"{sep}{num}"

            base = f"{name}{suffix}"
            combo = f"{base}:{base}"

            # Guaranteed no duplicates
            if combo in generated_set:
                continue

            f.write(combo + "\n")
            generated_set.add(combo)

            if len(generated_set) % 10000 == 0:
                print(f"[*] Progress: {len(generated_set)}/{count}...")

    print(f"\n[+] SUCCESS! Generated {len(generated_set)} unique combos.")
    print(f"[+] Saved to: {output_file}")


if __name__ == "__main__":
    generate_upass()