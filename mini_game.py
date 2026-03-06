import math
import random
import time
import tkinter as tk
from dataclasses import dataclass


ROWS = 5
COLS = 9
CELL_W = 92
CELL_H = 86
WORLD_W = COLS * CELL_W
WORLD_H = ROWS * CELL_H

ORIGIN_X = 74
ORIGIN_Y = 132
PERSPECTIVE = 0.11

CANVAS_W = 1000
CANVAS_H = 690

PLANT_INFO = {
    "sunflower": {"cost": 50, "hp": 8, "name": "向日葵"},
    "peashooter": {"cost": 100, "hp": 8, "name": "豌豆射手"},
    "wallnut": {"cost": 50, "hp": 60, "name": "坚果墙"},
    "snowpea": {"cost": 125, "hp": 8, "name": "寒冰射手"},
    "repeater": {"cost": 175, "hp": 9, "name": "双发射手"},
    "cherrybomb": {"cost": 150, "hp": 5, "name": "樱桃炸弹"},
}

ZOMBIE_INFO = {
    "normal": {"hp": 14, "speed": 0.66, "reward": 15, "attack_cd": 900, "bite": 1, "armor": 0},
    "cone": {"hp": 14, "speed": 0.58, "reward": 24, "attack_cd": 980, "bite": 1, "armor": 10},
    "bucket": {"hp": 16, "speed": 0.50, "reward": 34, "attack_cd": 1050, "bite": 1, "armor": 18},
    "runner": {"hp": 11, "speed": 1.12, "reward": 20, "attack_cd": 700, "bite": 1, "armor": 0},
    "spitter": {"hp": 13, "speed": 0.56, "reward": 26, "attack_cd": 1650, "bite": 1, "armor": 0},
}


@dataclass
class Plant:
    row: int
    col: int
    kind: str
    hp: int
    born_ms: float
    next_action_ms: float
    recoil_until_ms: float = 0.0
    hurt_until_ms: float = 0.0
    shake_until_ms: float = 0.0


@dataclass
class Zombie:
    row: int
    x: float
    kind: str
    hp: int
    speed: float
    reward: int
    attack_cd: int
    bite: int
    armor_hp: int
    next_attack_ms: float = 0.0
    slow_until_ms: float = 0.0
    state: str = "walk"
    state_until_ms: float = 0.0
    attack_cycle: int = 0
    hurt_until_ms: float = 0.0
    has_jumped: bool = False
    jumping: bool = False
    jump_from_x: float = 0.0
    jump_to_x: float = 0.0
    jump_start_ms: float = 0.0
    jump_end_ms: float = 0.0


@dataclass
class Projectile:
    row: int
    x: float
    damage: int
    speed: float
    color: str
    kind: str
    born_ms: float
    slow_ms: int = 0


@dataclass
class Explosion:
    row: int
    x: float
    born_ms: float
    expires_ms: float
    max_radius: float


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    size: float
    color: str
    born_ms: float
    expires_ms: float
    gravity: float = 0.05


@dataclass
class Mower:
    row: int
    x: float
    speed: float


class MiniPvZ:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("迷你植物大战僵尸 2.5D")
        self.root.resizable(False, False)

        self.sun = 225
        self.max_zombies = 38
        self.spawned = 0
        self.game_over = False
        self.game_win = False
        self.selected = "peashooter"
        self.stage_name = "前期"

        self.plants: dict[tuple[int, int], Plant] = {}
        self.zombies: list[Zombie] = []
        self.projectiles: list[Projectile] = []
        self.explosions: list[Explosion] = []
        self.particles: list[Particle] = []

        self.mower_ready = [True for _ in range(ROWS)]
        self.active_mowers: list[Mower] = []

        self.status_var = tk.StringVar()
        self.tip_var = tk.StringVar(value="快捷键 1-6 选植物，0 选铲子。点击草地种植。")
        self.card_buttons: dict[str, tk.Button] = {}

        self._build_ui()
        self._refresh_card_highlight()
        self._reset_timers()
        self._draw_static_scene()
        self._refresh_status()
        self.root.after(40, self._tick)

    @staticmethod
    def _now_ms() -> float:
        return time.monotonic() * 1000

    def _world_to_screen(self, x: float, y: float) -> tuple[float, float]:
        sx = ORIGIN_X + x
        sy = ORIGIN_Y + y - x * PERSPECTIVE
        return sx, sy

    def _screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        wx = sx - ORIGIN_X
        wy = sy - ORIGIN_Y + wx * PERSPECTIVE
        return wx, wy

    def _depth_scale(self, x: float) -> float:
        return 1.0 - 0.21 * (max(0.0, min(x, WORLD_W)) / WORLD_W)

    def _cell_center_x(self, col: int) -> float:
        return col * CELL_W + CELL_W * 0.5

    def _cell_center_y(self, row: int) -> float:
        return row * CELL_H + CELL_H * 0.62

    def _build_ui(self) -> None:
        top = tk.Frame(self.root, padx=8, pady=7, bg="#efe4c8")
        top.pack(fill="x")

        tk.Label(top, text="迷你植物大战僵尸 2.5D", bg="#efe4c8", fg="#2b2a24", font=("Microsoft YaHei", 14, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        tk.Label(top, textvariable=self.status_var, bg="#efe4c8", fg="#2d3f2f", font=("Consolas", 10, "bold")).grid(
            row=0, column=1, columnspan=8, sticky="w", padx=10
        )

        cards = [
            ("1 向日葵 50", "sunflower"),
            ("2 豌豆 100", "peashooter"),
            ("3 坚果 50", "wallnut"),
            ("4 寒冰 125", "snowpea"),
            ("5 双发 175", "repeater"),
            ("6 樱桃 150", "cherrybomb"),
        ]
        for idx, (label, key) in enumerate(cards):
            btn = tk.Button(top, text=label, width=12, command=lambda k=key: self._select(k))
            btn.grid(row=1, column=idx, padx=2, pady=4)
            self.card_buttons[key] = btn

        tk.Button(top, text="0 铲子", width=9, command=lambda: self._select("shovel")).grid(row=1, column=6, padx=4)
        tk.Button(top, text="重新开始", width=10, command=self._restart).grid(row=1, column=7, padx=4)
        tk.Label(top, textvariable=self.tip_var, bg="#efe4c8", fg="#39546a").grid(row=2, column=0, columnspan=9, sticky="w")

        self.canvas = tk.Canvas(self.root, width=CANVAS_W, height=CANVAS_H, bg="#8ec6f4", highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._on_click)

        self.root.bind("1", lambda _: self._select("sunflower"))
        self.root.bind("2", lambda _: self._select("peashooter"))
        self.root.bind("3", lambda _: self._select("wallnut"))
        self.root.bind("4", lambda _: self._select("snowpea"))
        self.root.bind("5", lambda _: self._select("repeater"))
        self.root.bind("6", lambda _: self._select("cherrybomb"))
        self.root.bind("0", lambda _: self._select("shovel"))

    def _select(self, kind: str) -> None:
        if self.game_over:
            return
        self.selected = kind
        if kind == "shovel":
            self.tip_var.set("已选择铲子。")
        else:
            info = PLANT_INFO[kind]
            self.tip_var.set(f"已选择 {info['name']}，消耗 {info['cost']} 阳光。")
        self._refresh_card_highlight()
        self._refresh_status()

    def _refresh_card_highlight(self) -> None:
        for key, btn in self.card_buttons.items():
            btn.configure(bg="#d6f2be" if key == self.selected else "SystemButtonFace")

    def _reset_timers(self) -> None:
        now = self._now_ms()
        self.next_spawn_ms = now + 4800
        self.next_passive_sun_ms = now + 9000

    def _current_level(self) -> tuple[str, int, tuple[int, int]]:
        ratio = self.spawned / max(1, self.max_zombies)
        if ratio < 0.30:
            return "前期", 1, (3000, 4200)
        if ratio < 0.60:
            return "中期", 2, (2300, 3200)
        if ratio < 0.88:
            return "后期", 3, (1600, 2400)
        return "终局", 4, (1200, 1850)

    def _pick_zombie_kind(self, level: int) -> str:
        roll = random.random()
        if level == 1:
            return "normal" if roll < 0.78 else "runner"
        if level == 2:
            if roll < 0.50:
                return "normal"
            if roll < 0.80:
                return "cone"
            return "runner"
        if level == 3:
            if roll < 0.30:
                return "normal"
            if roll < 0.56:
                return "cone"
            if roll < 0.78:
                return "bucket"
            if roll < 0.90:
                return "spitter"
            return "runner"
        if roll < 0.20:
            return "normal"
        if roll < 0.45:
            return "cone"
        if roll < 0.72:
            return "bucket"
        if roll < 0.90:
            return "spitter"
        return "runner"

    def _spawn_zombie(self) -> None:
        _, level, _ = self._current_level()
        kind = self._pick_zombie_kind(level)
        info = ZOMBIE_INFO[kind]
        hp = info["hp"] + (level - 1) * 2 + random.randint(0, 2)
        speed = info["speed"] + (0.02 * (level - 1))
        row = random.randint(0, ROWS - 1)
        self.zombies.append(
            Zombie(
                row=row,
                x=WORLD_W + 40,
                kind=kind,
                hp=hp,
                speed=speed,
                reward=info["reward"],
                attack_cd=info["attack_cd"],
                bite=info["bite"],
                armor_hp=info["armor"],
            )
        )
        self.spawned += 1

    def _on_click(self, event: tk.Event) -> None:
        if self.game_over:
            return
        wx, wy = self._screen_to_world(event.x, event.y)
        col = int(wx // CELL_W)
        row = int(wy // CELL_H)
        if not (0 <= row < ROWS and 0 <= col < COLS):
            return
        pos = (row, col)

        if self.selected == "shovel":
            if pos in self.plants:
                del self.plants[pos]
                self.tip_var.set("已移除植物。")
            else:
                self.tip_var.set("这里没有植物。")
            return

        if pos in self.plants:
            self.tip_var.set("该位置已有植物。")
            return
        info = PLANT_INFO[self.selected]
        if self.sun < info["cost"]:
            self.tip_var.set("阳光不足。")
            return

        self.sun -= info["cost"]
        now = self._now_ms()
        delay = {
            "sunflower": 6500,
            "peashooter": 1220,
            "wallnut": 10**9,
            "snowpea": 1420,
            "repeater": 1520,
            "cherrybomb": 980,
        }[self.selected]
        self.plants[pos] = Plant(row=row, col=col, kind=self.selected, hp=info["hp"], born_ms=now, next_action_ms=now + delay)
        self.tip_var.set(f"已种下 {info['name']}。")

    def _row_has_front_zombie(self, row: int, x: float) -> bool:
        return any(z.hp > 0 and z.row == row and z.x + 56 > x for z in self.zombies)

    def _zombie_blocking_plant(self, zombie: Zombie) -> Plant | None:
        overlapped: list[Plant] = []
        for plant in self.plants.values():
            if plant.row != zombie.row:
                continue
            px0 = plant.col * CELL_W + 8
            px1 = (plant.col + 1) * CELL_W - 8
            zx0 = zombie.x
            zx1 = zombie.x + 56
            if zx1 > px0 and zx0 < px1:
                overlapped.append(plant)
        return max(overlapped, key=lambda p: p.col) if overlapped else None

    def _nearest_front_plant(self, row: int, zombie_x: float) -> tuple[Plant | None, float]:
        nearest = None
        best_dist = 10**9
        z_center = zombie_x + 28
        for plant in self.plants.values():
            if plant.row != row:
                continue
            dist = z_center - self._cell_center_x(plant.col)
            if 0 <= dist < best_dist:
                nearest = plant
                best_dist = dist
        return nearest, best_dist

    def _spawn_projectile(
        self,
        row: int,
        x: float,
        damage: int,
        speed: float,
        color: str,
        kind: str,
        now: float,
        slow_ms: int = 0,
    ) -> None:
        self.projectiles.append(
            Projectile(row=row, x=x, damage=damage, speed=speed, color=color, kind=kind, born_ms=now, slow_ms=slow_ms)
        )

    def _damage_plant(self, plant: Plant, damage: int, now: float) -> None:
        plant.hp -= damage
        plant.hurt_until_ms = now + 170
        plant.shake_until_ms = now + 230

    def _spawn_sparks(self, x: float, y: float, now: float, count: int, color: str, spread: float = 2.4) -> None:
        for _ in range(count):
            ang = random.uniform(-math.pi, math.pi)
            speed = random.uniform(0.8, spread)
            self.particles.append(
                Particle(
                    x=x,
                    y=y,
                    vx=math.cos(ang) * speed,
                    vy=math.sin(ang) * speed - random.uniform(0.2, 1.1),
                    size=random.uniform(2.0, 4.2),
                    color=color,
                    born_ms=now,
                    expires_ms=now + random.uniform(220, 620),
                    gravity=0.06,
                )
            )

    def _damage_zombie(self, zombie: Zombie, damage: int, now: float) -> None:
        zombie.hurt_until_ms = now + 120
        if zombie.armor_hp > 0:
            zombie.armor_hp -= damage
            if zombie.armor_hp <= 0:
                overflow = -zombie.armor_hp
                zombie.armor_hp = 0
                zombie.state = "armor_break"
                zombie.state_until_ms = now + 260
                self._spawn_sparks(zombie.x + 22, zombie.row * CELL_H + CELL_H * 0.4, now, 9, "#c8d4de", 2.8)
                if overflow > 0:
                    zombie.hp -= overflow
        else:
            zombie.hp -= damage

    def _explode(self, row: int, col: int, now: float) -> None:
        cx = self._cell_center_x(col)
        cy = self._cell_center_y(row)
        radius = CELL_W * 1.85
        for zombie in self.zombies:
            if zombie.hp <= 0:
                continue
            zx = zombie.x + 28
            zy = self._cell_center_y(zombie.row)
            dist = math.hypot(zx - cx, (zy - cy) * 1.22)
            if dist <= radius:
                ratio = 1.0 - dist / radius
                self._damage_zombie(zombie, int(12 + ratio * 34), now)
        self.explosions.append(Explosion(row=row, x=cx, born_ms=now, expires_ms=now + 650, max_radius=CELL_W * 2.6))
        self._spawn_sparks(cx, cy - 4, now, 38, "#ff9e35", 4.8)
        self._spawn_sparks(cx, cy - 2, now, 26, "#ffe085", 3.5)

    def _update_plants(self, now: float) -> None:
        for key, plant in list(self.plants.items()):
            if plant.hp <= 0:
                self.plants.pop(key, None)
                continue
            if now < plant.next_action_ms:
                continue
            shoot_x = plant.col * CELL_W + CELL_W * 0.72
            if plant.kind == "sunflower":
                self.sun += 30
                plant.recoil_until_ms = now + 450
                plant.next_action_ms = now + 6500
            elif plant.kind == "peashooter":
                if self._row_has_front_zombie(plant.row, shoot_x):
                    self._spawn_projectile(plant.row, shoot_x, 1, 8.2, "#2a9d39", "pea", now)
                    plant.recoil_until_ms = now + 190
                plant.next_action_ms = now + 1220
            elif plant.kind == "snowpea":
                if self._row_has_front_zombie(plant.row, shoot_x):
                    self._spawn_projectile(plant.row, shoot_x, 1, 7.6, "#7edbff", "ice", now, slow_ms=2800)
                    plant.recoil_until_ms = now + 220
                plant.next_action_ms = now + 1420
            elif plant.kind == "repeater":
                if self._row_has_front_zombie(plant.row, shoot_x):
                    self._spawn_projectile(plant.row, shoot_x, 1, 8.6, "#39ae46", "pea", now)
                    self._spawn_projectile(plant.row, shoot_x - 14, 1, 8.9, "#2f9a3e", "pea", now)
                    plant.recoil_until_ms = now + 250
                plant.next_action_ms = now + 1520
            elif plant.kind == "cherrybomb":
                self._explode(plant.row, plant.col, now)
                self.plants.pop(key, None)

    def _update_projectiles(self, now: float) -> None:
        alive: list[Projectile] = []
        for p in self.projectiles:
            prev_x = p.x
            p.x += p.speed
            if p.kind == "spit":
                hit = None
                for plant in self.plants.values():
                    if plant.row != p.row:
                        continue
                    px0 = plant.col * CELL_W + 8
                    px1 = (plant.col + 1) * CELL_W - 8
                    if prev_x >= px0 and p.x <= px1:
                        hit = plant
                        break
                if hit:
                    self._damage_plant(hit, p.damage, now)
                    self._spawn_sparks(p.x, hit.row * CELL_H + CELL_H * 0.56, now, 6, "#98cc6b", 1.9)
                elif p.x >= -40:
                    alive.append(p)
                continue

            hit_z = None
            hit_x = 10**9
            for zombie in self.zombies:
                if zombie.hp <= 0 or zombie.row != p.row:
                    continue
                zx0 = zombie.x
                zx1 = zombie.x + 56
                if prev_x <= zx1 and p.x >= zx0 and zx0 < hit_x:
                    hit_x = zx0
                    hit_z = zombie
            if hit_z:
                self._damage_zombie(hit_z, p.damage, now)
                if p.slow_ms > 0:
                    hit_z.slow_until_ms = max(hit_z.slow_until_ms, now + p.slow_ms)
                self._spawn_sparks(hit_z.x + 18, hit_z.row * CELL_H + CELL_H * 0.45, now, 4, "#c7f2ff" if p.kind == "ice" else "#8fd67a", 1.5)
            elif p.x <= WORLD_W + 70:
                alive.append(p)
        self.projectiles = alive

    def _resolve_melee_attack(self, zombie: Zombie) -> tuple[int, int, str, int]:
        zombie.attack_cycle += 1
        if zombie.kind == "cone":
            return (2, zombie.attack_cd + 220, "headbutt", 300) if zombie.attack_cycle % 3 == 0 else (1, zombie.attack_cd, "bite", 210)
        if zombie.kind == "bucket":
            return (3, zombie.attack_cd + 280, "smash", 360) if zombie.attack_cycle % 2 == 0 else (1, zombie.attack_cd, "bite", 230)
        if zombie.kind == "runner":
            cd = max(430, zombie.attack_cd - 180)
            return (2, cd, "claw", 220) if zombie.attack_cycle % 4 == 0 else (1, cd, "bite", 180)
        if zombie.kind == "spitter":
            return 1, 980, "bite", 210
        return zombie.bite, zombie.attack_cd, "bite", 220

    def _try_runner_jump(self, zombie: Zombie, target: Plant, now: float) -> bool:
        if zombie.kind != "runner" or zombie.has_jumped or zombie.jumping or target.kind == "wallnut":
            return False
        zombie.has_jumped = True
        zombie.jumping = True
        zombie.state = "jump"
        zombie.state_until_ms = now + 420
        zombie.jump_start_ms = now
        zombie.jump_end_ms = now + 420
        zombie.jump_from_x = zombie.x
        zombie.jump_to_x = max(-10, zombie.x - CELL_W * 0.95)
        return True

    def _update_zombies(self, now: float) -> None:
        for zombie in self.zombies:
            if zombie.hp <= 0:
                continue
            if zombie.jumping:
                dur = max(1.0, zombie.jump_end_ms - zombie.jump_start_ms)
                p = (now - zombie.jump_start_ms) / dur
                if p >= 1.0:
                    zombie.jumping = False
                    zombie.x = zombie.jump_to_x
                    zombie.state = "walk"
                else:
                    zombie.x = zombie.jump_from_x + (zombie.jump_to_x - zombie.jump_from_x) * p
                continue

            block = self._zombie_blocking_plant(zombie)
            speed = zombie.speed * (0.56 if now < zombie.slow_until_ms else 1.0)
            if block is None:
                if zombie.kind == "spitter":
                    target, dist = self._nearest_front_plant(zombie.row, zombie.x)
                    if target and CELL_W * 0.72 < dist < CELL_W * 2.6 and now >= zombie.next_attack_ms:
                        self._spawn_projectile(zombie.row, zombie.x + 10, 1, -4.8, "#87bb5c", "spit", now)
                        zombie.next_attack_ms = now + zombie.attack_cd
                        zombie.state = "spit"
                        zombie.state_until_ms = now + 280
                    else:
                        zombie.x -= speed
                        if now >= zombie.state_until_ms:
                            zombie.state = "walk"
                else:
                    zombie.x -= speed
                    if now >= zombie.state_until_ms:
                        zombie.state = "walk"
            else:
                if self._try_runner_jump(zombie, block, now):
                    continue
                if now >= zombie.next_attack_ms:
                    damage, cd, state, dur = self._resolve_melee_attack(zombie)
                    if state == "headbutt":
                        zombie.x -= 4
                    self._damage_plant(block, damage, now)
                    zombie.next_attack_ms = now + cd
                    zombie.state = state
                    zombie.state_until_ms = now + dur
                elif now >= zombie.state_until_ms:
                    zombie.state = "idle"

            if zombie.x <= 0:
                if not self._trigger_mower(zombie.row):
                    self._end(False)
                    return
                zombie.x = 12
                zombie.state = "stagger"
                zombie.state_until_ms = now + 280

    def _trigger_mower(self, row: int) -> bool:
        if not self.mower_ready[row]:
            return False
        self.mower_ready[row] = False
        self.active_mowers.append(Mower(row=row, x=-35, speed=8.4))
        self.tip_var.set(f"第 {row + 1} 路小推车已触发。")
        return True

    def _update_mowers(self, now: float) -> None:
        alive: list[Mower] = []
        for mower in self.active_mowers:
            mower.x += mower.speed
            for zombie in self.zombies:
                if zombie.hp <= 0 or zombie.row != mower.row:
                    continue
                if zombie.x + 56 >= mower.x - 8 and zombie.x <= mower.x + 44:
                    zombie.hp = 0
                    self._spawn_sparks(zombie.x + 24, zombie.row * CELL_H + CELL_H * 0.5, now, 12, "#cfd6dd", 2.4)
            if mower.x <= WORLD_W + 80:
                alive.append(mower)
        self.active_mowers = alive

    def _update_particles(self, now: float) -> None:
        alive: list[Particle] = []
        for p in self.particles:
            p.x += p.vx
            p.y += p.vy
            p.vy += p.gravity
            if now <= p.expires_ms:
                alive.append(p)
        self.particles = alive

    def _cleanup_units(self, now: float) -> None:
        survivors: list[Zombie] = []
        for zombie in self.zombies:
            if zombie.hp <= 0:
                self.sun += zombie.reward
                self._spawn_sparks(zombie.x + 22, zombie.row * CELL_H + CELL_H * 0.52, now, 8, "#9eadb2", 2.0)
            else:
                survivors.append(zombie)
        self.zombies = survivors
        self.explosions = [e for e in self.explosions if now <= e.expires_ms]
        for key, plant in list(self.plants.items()):
            if plant.hp <= 0:
                self.plants.pop(key, None)

    def _draw_static_scene(self) -> None:
        self.canvas.delete("static")

        for i in range(22):
            t = i / 21
            r = int(128 + 38 * t)
            g = int(180 + 42 * t)
            b = int(246 - 26 * t)
            y0 = int(i * 18)
            self.canvas.create_rectangle(0, y0, CANVAS_W, y0 + 19, fill=f"#{r:02x}{g:02x}{b:02x}", outline="", tags="static")

        self.canvas.create_polygon(
            610, 168, 685, 108, 760, 168, 850, 94, 935, 168, CANVAS_W, 168, CANVAS_W, 240, 610, 240, fill="#9db6ba", outline="", tags="static"
        )
        self.canvas.create_polygon(
            550, 190, 635, 138, 730, 190, 820, 132, 925, 190, CANVAS_W, 190, CANVAS_W, 248, 550, 248, fill="#89a5aa", outline="", tags="static"
        )

        cloud_groups = [
            (712, 56, 1.0),
            (858, 88, 0.82),
            (634, 94, 0.76),
            (932, 58, 0.62),
        ]
        for cx, cy, scale in cloud_groups:
            w = 102 * scale
            h = 44 * scale
            self.canvas.create_oval(cx - w * 0.55, cy - h * 0.46, cx - w * 0.05, cy + h * 0.46, fill="#f3f8ff", outline="", tags="static")
            self.canvas.create_oval(cx - w * 0.18, cy - h * 0.58, cx + w * 0.38, cy + h * 0.42, fill="#f7fbff", outline="", tags="static")
            self.canvas.create_oval(cx + w * 0.1, cy - h * 0.34, cx + w * 0.58, cy + h * 0.44, fill="#edf5ff", outline="", tags="static")
            self.canvas.create_oval(cx - w * 0.5, cy + h * 0.1, cx + w * 0.62, cy + h * 0.58, fill="#dbe9f7", outline="", tags="static")

        self.canvas.create_rectangle(0, 126, CANVAS_W, 154, fill="#578f4f", outline="", tags="static")

        self.canvas.create_rectangle(6, 164, 64, 635, fill="#d9ca95", outline="#9b8d65", width=2, tags="static")
        self.canvas.create_rectangle(17, 222, 52, 280, fill="#7d4a42", outline="#5f352f", tags="static")
        self.canvas.create_rectangle(17, 348, 52, 408, fill="#7d4a42", outline="#5f352f", tags="static")
        self.canvas.create_rectangle(17, 474, 52, 534, fill="#7d4a42", outline="#5f352f", tags="static")

        for row in range(ROWS):
            lane_color = "#88c670" if row % 2 == 0 else "#7ebf68"
            x0, y0 = self._world_to_screen(0, row * CELL_H)
            x1, y1 = self._world_to_screen(WORLD_W, row * CELL_H)
            x2, y2 = self._world_to_screen(WORLD_W, (row + 1) * CELL_H)
            x3, y3 = self._world_to_screen(0, (row + 1) * CELL_H)
            self.canvas.create_polygon(x0, y0, x1, y1, x2, y2, x3, y3, fill=lane_color, outline="#6ea95a", tags="static")

        for row in range(ROWS):
            for col in range(COLS):
                x0, y0 = self._world_to_screen(col * CELL_W, row * CELL_H)
                x1, y1 = self._world_to_screen((col + 1) * CELL_W, row * CELL_H)
                x2, y2 = self._world_to_screen((col + 1) * CELL_W, (row + 1) * CELL_H)
                x3, y3 = self._world_to_screen(col * CELL_W, (row + 1) * CELL_H)
                color = "#8ecf76" if (row + col) % 2 == 0 else "#85c86e"
                self.canvas.create_polygon(
                    x0 + 1,
                    y0 + 1,
                    x1 - 1,
                    y1 + 1,
                    x2 - 1,
                    y2 - 1,
                    x3 + 1,
                    y3 - 1,
                    fill=color,
                    outline="#72b35e",
                    tags="static",
                )
                # subtle blade texture
                cx = (x0 + x1 + x2 + x3) / 4
                cy = (y0 + y1 + y2 + y3) / 4
                self.canvas.create_line(cx - 8, cy + 3, cx - 2, cy - 5, fill="#7dbf66", width=1, tags="static")
                self.canvas.create_line(cx + 2, cy + 5, cx + 9, cy - 3, fill="#7ab862", width=1, tags="static")

        self.canvas.create_polygon(
            ORIGIN_X + WORLD_W + 2,
            ORIGIN_Y - WORLD_W * PERSPECTIVE - 8,
            CANVAS_W,
            140,
            CANVAS_W,
            CANVAS_H,
            ORIGIN_X + WORLD_W + 2,
            ORIGIN_Y + WORLD_H - WORLD_W * PERSPECTIVE + 8,
            fill="#7ca26f",
            outline="",
            tags="static",
        )
        self.canvas.create_line(
            ORIGIN_X + WORLD_W + 2,
            ORIGIN_Y - WORLD_W * PERSPECTIVE - 8,
            ORIGIN_X + WORLD_W + 2,
            ORIGIN_Y + WORLD_H - WORLD_W * PERSPECTIVE + 8,
            fill="#68905e",
            width=2,
            tags="static",
        )

    def _draw_plant(self, plant: Plant, now: float) -> None:
        x = self._cell_center_x(plant.col)
        y = self._cell_center_y(plant.row)
        sx, sy = self._world_to_screen(x, y)
        s = self._depth_scale(x)
        sy += math.sin(now * 0.006 + plant.col * 0.7 + plant.row * 0.5) * 1.5 * s
        if now < plant.shake_until_ms:
            sx += math.sin(now * 0.09 + plant.col * 1.4) * 3.3 * s

        hurt = now < plant.hurt_until_ms
        border = "#9b1f1f" if hurt else "#402820"
        recoil = max(0.0, min(1.0, (plant.recoil_until_ms - now) / 260.0))
        recoil_dx = -7.0 * recoil * s

        # ground shadow
        self.canvas.create_oval(sx - 23 * s, sy + 9 * s, sx + 23 * s, sy + 20 * s, fill="#26492a", outline="", tags="dynamic")
        self.canvas.create_oval(sx - 16 * s, sy + 11 * s, sx + 16 * s, sy + 18 * s, fill="#2f6434", outline="", tags="dynamic")

        if plant.kind == "sunflower":
            glow = max(0.0, min(1.0, (plant.recoil_until_ms - now) / 450.0))
            if glow > 0:
                gr = 30 * s * (0.45 + glow)
                self.canvas.create_oval(
                    sx - gr,
                    sy - 32 * s - gr * 0.5,
                    sx + gr,
                    sy - 8 * s + gr * 0.5,
                    outline="#f6e084",
                    width=2,
                    tags="dynamic",
                )
            spin = now * 0.0028
            for i in range(12):
                ang = spin + i * (2 * math.pi / 12)
                px = sx + math.cos(ang) * 14 * s
                py = sy - 11 * s + math.sin(ang) * 9 * s
                self.canvas.create_oval(px - 6.5 * s, py - 6.5 * s, px + 6.5 * s, py + 6.5 * s, fill="#f4cc34", outline="#c7971e", width=1, tags="dynamic")
                self.canvas.create_oval(px - 2.2 * s, py - 2.2 * s, px + 0.8 * s, py + 0.8 * s, fill="#fff6be", outline="", tags="dynamic")
            self.canvas.create_oval(sx - 11 * s, sy - 18 * s, sx + 11 * s, sy + 4 * s, fill="#b16060" if hurt else "#8f5e2a", outline=border, width=2, tags="dynamic")
            self.canvas.create_oval(sx - 4 * s, sy - 15 * s, sx + 4 * s, sy - 10 * s, fill="#a77641", outline="", tags="dynamic")
            self.canvas.create_oval(sx - 4 * s, sy - 10 * s, sx - 1 * s, sy - 7 * s, fill="#171717", outline="", tags="dynamic")
            self.canvas.create_oval(sx + 1 * s, sy - 10 * s, sx + 4 * s, sy - 7 * s, fill="#171717", outline="", tags="dynamic")
            self.canvas.create_arc(sx - 6 * s, sy - 5 * s, sx + 6 * s, sy + 2 * s, start=205, extent=130, style="arc", width=1, tags="dynamic")
            self.canvas.create_line(sx, sy + 10 * s, sx, sy - 19 * s, fill="#3f7e2c", width=3, tags="dynamic")
            self.canvas.create_oval(sx - 11 * s, sy - 2 * s, sx - 2 * s, sy + 6 * s, fill="#4a8f39", outline="", tags="dynamic")
            self.canvas.create_oval(sx + 2 * s, sy + 0 * s, sx + 11 * s, sy + 8 * s, fill="#4a8f39", outline="", tags="dynamic")

        elif plant.kind in {"peashooter", "snowpea", "repeater"}:
            fill = "#5bd067" if plant.kind == "peashooter" else "#89e7ff" if plant.kind == "snowpea" else "#54c55f"
            edge = "#2f7b3f" if plant.kind != "snowpea" else "#4aa1c6"
            self.canvas.create_line(sx - 2 * s, sy + 10 * s, sx - 2 * s, sy - 20 * s, fill="#3b8c2f", width=5 if plant.kind == "repeater" else 4, tags="dynamic")
            self.canvas.create_oval(sx - 15 * s, sy + 2 * s, sx - 3 * s, sy + 10 * s, fill="#4c9a3c", outline="", tags="dynamic")
            self.canvas.create_oval(sx + 0 * s, sy + 3 * s, sx + 12 * s, sy + 11 * s, fill="#4c9a3c", outline="", tags="dynamic")
            head_x = sx + recoil_dx
            if plant.kind == "repeater":
                self.canvas.create_oval(head_x - 20 * s, sy - 34 * s, head_x + 7 * s, sy - 8 * s, fill=fill, outline=edge, width=2, tags="dynamic")
                self.canvas.create_oval(head_x + 2 * s, sy - 31 * s, head_x + 27 * s, sy - 6 * s, fill=fill, outline=edge, width=2, tags="dynamic")
                self.canvas.create_oval(head_x + 23 * s, sy - 24 * s, head_x + 34 * s, sy - 14 * s, fill=fill, outline=edge, width=2, tags="dynamic")
                self.canvas.create_oval(head_x + 10 * s, sy - 28 * s, head_x + 16 * s, sy - 23 * s, fill="#eef9ea", outline="", tags="dynamic")
            else:
                self.canvas.create_oval(head_x - 16 * s, sy - 32 * s, head_x + 16 * s, sy - 6 * s, fill=fill, outline=edge, width=2, tags="dynamic")
                self.canvas.create_oval(head_x + 10 * s, sy - 24 * s, head_x + 23 * s, sy - 14 * s, fill=fill, outline=edge, width=2, tags="dynamic")
                self.canvas.create_oval(head_x - 5 * s, sy - 27 * s, head_x + 0 * s, sy - 22 * s, fill="#eef9ea", outline="", tags="dynamic")
            self.canvas.create_oval(head_x - 3 * s, sy - 18 * s, head_x + 2 * s, sy - 13 * s, fill="#2d5232", outline="", tags="dynamic")
            if plant.kind == "snowpea":
                self.canvas.create_oval(head_x - 13 * s, sy - 17 * s, head_x + 11 * s, sy - 5 * s, outline="#d5f5ff", width=1, tags="dynamic")
            if recoil > 0.12:
                flash_r = (7 + 6 * recoil) * s
                mx = head_x + 26 * s
                my = sy - 19 * s
                self.canvas.create_oval(mx - flash_r, my - flash_r * 0.72, mx + flash_r, my + flash_r * 0.72, fill="#f7e96e", outline="#e2ac2d", tags="dynamic")
                self.canvas.create_line(mx + 2 * s, my - 2 * s, mx + 9 * s, my - 6 * s, fill="#ffd98e", width=2, tags="dynamic")

        elif plant.kind == "wallnut":
            self.canvas.create_oval(sx - 19 * s, sy - 25 * s, sx + 19 * s, sy + 8 * s, fill="#c16565" if hurt else "#b98349", outline=border, width=2, tags="dynamic")
            self.canvas.create_oval(sx - 9 * s, sy - 20 * s, sx + 2 * s, sy - 14 * s, fill="#cb9a60", outline="", tags="dynamic")
            self.canvas.create_oval(sx - 5 * s, sy - 12 * s, sx - 2 * s, sy - 9 * s, fill="#1f1f1f", outline="", tags="dynamic")
            self.canvas.create_oval(sx + 2 * s, sy - 12 * s, sx + 5 * s, sy - 9 * s, fill="#1f1f1f", outline="", tags="dynamic")
            self.canvas.create_arc(sx - 7 * s, sy - 6 * s, sx + 7 * s, sy + 4 * s, start=200, extent=140, style="arc", width=2, tags="dynamic")
            if plant.hp < 38:
                self.canvas.create_line(sx - 6 * s, sy - 15 * s, sx + 2 * s, sy - 4 * s, fill="#6f4420", width=2, tags="dynamic")
            if plant.hp < 20:
                self.canvas.create_line(sx + 7 * s, sy - 17 * s, sx + 11 * s, sy - 6 * s, fill="#6f4420", width=2, tags="dynamic")

        elif plant.kind == "cherrybomb":
            remain = max(0.0, plant.next_action_ms - now)
            urgency = 1.0 - min(1.0, remain / 980.0)
            pulse = 1.0 + (0.07 + urgency * 0.1) * math.sin(now * (0.016 + urgency * 0.03))
            cs = s * pulse
            self.canvas.create_line(sx, sy + 10 * s, sx, sy - 12 * s, fill="#2f772c", width=4, tags="dynamic")
            self.canvas.create_oval(sx - 17 * cs, sy - 24 * cs, sx - 1 * cs, sy - 8 * cs, fill="#df3840", outline="#8b1f25", width=2, tags="dynamic")
            self.canvas.create_oval(sx + 1 * cs, sy - 24 * cs, sx + 17 * cs, sy - 8 * cs, fill="#df3840", outline="#8b1f25", width=2, tags="dynamic")
            self.canvas.create_oval(sx - 12 * cs, sy - 21 * cs, sx - 5 * cs, sy - 15 * cs, fill="#f1767b", outline="", tags="dynamic")
            self.canvas.create_oval(sx + 4 * cs, sy - 21 * cs, sx + 11 * cs, sy - 15 * cs, fill="#f1767b", outline="", tags="dynamic")
            fx, fy = sx + 4 * s, sy - 31 * s
            self.canvas.create_line(sx - 2 * s, sy - 24 * s, fx, fy, fill="#6a4f25", width=2, tags="dynamic")
            orbit = now * 0.02
            spark_x = fx + math.cos(orbit) * (2 + urgency * 2)
            spark_y = fy + math.sin(orbit) * 2
            self.canvas.create_oval(spark_x - 4, spark_y - 4, spark_x + 4, spark_y + 4, fill="#ffde7d", outline="#f58a2d", tags="dynamic")
            self.canvas.create_line(spark_x - 2, spark_y - 2, spark_x - 7, spark_y - 6, fill="#ffd17d", width=2, tags="dynamic")
            self.canvas.create_line(spark_x + 1, spark_y + 1, spark_x + 6, spark_y + 5, fill="#ffd17d", width=2, tags="dynamic")
            if urgency > 0.65:
                ring = 18 * s * (0.6 + urgency)
                self.canvas.create_oval(
                    sx - ring,
                    sy - 19 * s - ring * 0.4,
                    sx + ring,
                    sy - 19 * s + ring * 0.4,
                    outline="#ff9d40",
                    width=2,
                    tags="dynamic",
                )
                self.canvas.create_oval(
                    sx - ring * 0.55,
                    sy - 19 * s - ring * 0.22,
                    sx + ring * 0.55,
                    sy - 19 * s + ring * 0.22,
                    outline="#ffbf73",
                    width=1,
                    tags="dynamic",
                )

        self.canvas.create_text(
            sx,
            sy + 24 * s,
            text=f"血量 {plant.hp}",
            fill="#1a3a1a",
            font=("Microsoft YaHei", max(8, int(8 * s))),
            tags="dynamic",
        )

    def _draw_zombie(self, zombie: Zombie, now: float) -> None:
        x = zombie.x + 24
        y = self._cell_center_y(zombie.row)
        sx, sy = self._world_to_screen(x, y)
        s = self._depth_scale(zombie.x)

        phase = now * 0.007 + zombie.row * 0.9 + zombie.x * 0.02
        stride = math.sin(phase) * 4.0 * s
        sy -= math.sin(phase * 2.0) * 1.4 * s
        attack = max(0.0, min(1.0, (zombie.state_until_ms - now) / 380.0)) if zombie.state in {"bite", "claw", "headbutt", "smash", "spit"} else 0.0
        if zombie.jumping:
            dur = max(1.0, zombie.jump_end_ms - zombie.jump_start_ms)
            p = max(0.0, min(1.0, (now - zombie.jump_start_ms) / dur))
            sy -= math.sin(p * math.pi) * 29.0 * s

        cloth = {"normal": "#596487", "cone": "#5a6a82", "bucket": "#4f5662", "runner": "#6a4f76", "spitter": "#5f7e56"}[zombie.kind]
        skin = {"normal": "#d4ddd5", "cone": "#d8ded6", "bucket": "#d2d9d3", "runner": "#d5dfd7", "spitter": "#c9dfc7"}[zombie.kind]
        if now < zombie.hurt_until_ms:
            cloth = "#a06666"

        self.canvas.create_oval(sx - 22 * s, sy + 10 * s, sx + 22 * s, sy + 19 * s, fill="#374046", outline="", tags="dynamic")
        self.canvas.create_oval(sx - 14 * s, sy + 12 * s, sx + 14 * s, sy + 18 * s, fill="#455157", outline="", tags="dynamic")
        lean = -6.5 * s if zombie.state == "headbutt" else -4.8 * s if zombie.state == "smash" else 4.2 * s if zombie.state == "spit" else 0.0
        self.canvas.create_rectangle(sx - 15 * s + lean, sy - 25 * s, sx + 15 * s + lean * 0.35, sy + 8 * s, fill=cloth, outline="#4d5c5f", width=2, tags="dynamic")
        self.canvas.create_rectangle(sx - 14 * s + lean, sy - 22 * s, sx - 6 * s + lean * 0.3, sy + 5 * s, fill="#4d5671", outline="", tags="dynamic")
        self.canvas.create_rectangle(sx + 5 * s + lean * 0.2, sy - 22 * s, sx + 13 * s + lean * 0.3, sy + 5 * s, fill="#6a748f", outline="", tags="dynamic")

        self.canvas.create_line(sx - 8 * s, sy + 8 * s, sx - 10 * s + stride, sy + 17 * s, fill="#303b40", width=3, tags="dynamic")
        self.canvas.create_line(sx + 4 * s, sy + 8 * s, sx + 7 * s - stride, sy + 17 * s, fill="#303b40", width=3, tags="dynamic")
        self.canvas.create_line(sx - 10 * s + stride, sy + 17 * s, sx - 5 * s + stride, sy + 17 * s, fill="#252d32", width=3, tags="dynamic")
        self.canvas.create_line(sx + 7 * s - stride, sy + 17 * s, sx + 12 * s - stride, sy + 17 * s, fill="#252d32", width=3, tags="dynamic")

        reach = 3.0 * s + attack * 7.5 * s
        self.canvas.create_line(sx + 8 * s + lean * 0.15, sy - 10 * s, sx + 16 * s + reach, sy - 5 * s + attack * 2 * s, fill=skin, width=4, tags="dynamic")
        self.canvas.create_line(sx + 7 * s + lean * 0.1, sy - 3 * s, sx + 15 * s + reach * 0.8, sy + 2 * s + attack * 1.2 * s, fill=skin, width=4, tags="dynamic")

        self.canvas.create_oval(sx - 11 * s + lean * 0.2, sy - 40 * s, sx + 8 * s + lean * 0.2, sy - 20 * s, fill=skin, outline="#5f6a62", width=2, tags="dynamic")
        self.canvas.create_oval(sx - 7 * s, sy - 34 * s, sx - 1.5 * s, sy - 28.5 * s, fill="#1a1a1a", outline="", tags="dynamic")
        self.canvas.create_oval(sx - 5.9 * s, sy - 33.2 * s, sx - 4.8 * s, sy - 32.1 * s, fill="#f3f6f8", outline="", tags="dynamic")
        self.canvas.create_oval(sx + 0.2 * s, sy - 33.8 * s, sx + 5.4 * s, sy - 28.8 * s, fill="#1a1a1a", outline="", tags="dynamic")
        self.canvas.create_oval(sx + 1.4 * s, sy - 32.7 * s, sx + 2.4 * s, sy - 31.7 * s, fill="#f3f6f8", outline="", tags="dynamic")
        self.canvas.create_rectangle(sx - 1 * s, sy - 26 * s, sx + 8 * s, sy - 25 * s + (2.0 + attack * 4.8) * s, fill="#6d2c2c", outline="", tags="dynamic")
        self.canvas.create_line(sx + 1 * s, sy - 24 * s, sx + 7 * s, sy - 24 * s, fill="#e9e5d7", width=1, tags="dynamic")

        if zombie.kind == "cone":
            dmg = 1.0 - zombie.armor_hp / max(1, ZOMBIE_INFO["cone"]["armor"])
            tip = 68 - dmg * 8
            self.canvas.create_polygon(sx - 7 * s, sy - 45 * s, sx + 12 * s, sy - 45 * s, sx + 2 * s, sy - tip * s, fill="#d78a2f", outline="#9f5f1f", width=2, tags="dynamic")
            self.canvas.create_line(sx + 2 * s, sy - 64 * s, sx + 2 * s, sy - 45 * s, fill="#f3b865", width=1, tags="dynamic")
            self.canvas.create_line(sx - 2 * s, sy - 54 * s, sx + 5 * s, sy - 54 * s, fill="#be7421", width=1, tags="dynamic")
        elif zombie.kind == "bucket":
            self.canvas.create_rectangle(sx - 11 * s, sy - 54 * s, sx + 12 * s, sy - 38 * s, fill="#a4aeb8" if zombie.armor_hp > 0 else "#747e85", outline="#59616a", width=2, tags="dynamic")
            self.canvas.create_rectangle(sx - 10 * s, sy - 51 * s, sx + 11 * s, sy - 48 * s, fill="#c5d0da", outline="", tags="dynamic")
            self.canvas.create_line(sx - 2 * s, sy - 54 * s, sx - 2 * s, sy - 38 * s, fill="#7d8892", width=1, tags="dynamic")
        elif zombie.kind == "runner":
            self.canvas.create_polygon(
                sx - 12 * s,
                sy - 39 * s,
                sx + 7 * s,
                sy - 39 * s,
                sx + 1 * s,
                sy - 28 * s,
                sx - 8 * s,
                sy - 28 * s,
                fill="#4f3f62",
                outline="#3a2e4a",
                width=2,
                tags="dynamic",
            )
            self.canvas.create_line(sx - 8 * s, sy - 30 * s, sx + 8 * s, sy - 34 * s, fill="#cc4453", width=3, tags="dynamic")
            self.canvas.create_line(sx - 5 * s, sy - 36 * s, sx + 3 * s, sy - 38 * s, fill="#b03645", width=2, tags="dynamic")
        elif zombie.kind == "spitter":
            self.canvas.create_oval(sx + 6 * s, sy - 29 * s, sx + 12 * s, sy - 23 * s, fill="#7aac52", outline="#5e8940", tags="dynamic")
            if zombie.state == "spit" and now < zombie.state_until_ms:
                self.canvas.create_line(sx + 10 * s, sy - 25 * s, sx + 18 * s, sy - 22 * s, fill="#8ec061", width=2, tags="dynamic")
            self.canvas.create_oval(sx - 12 * s, sy - 24 * s, sx + 2 * s, sy - 13 * s, outline="#9dce79", width=1, tags="dynamic")

        if now < zombie.slow_until_ms:
            self.canvas.create_oval(sx - 24 * s, sy - 46 * s, sx + 22 * s, sy + 19 * s, outline="#84d8ff", width=2, tags="dynamic")
            self.canvas.create_oval(sx - 17 * s, sy - 39 * s, sx + 14 * s, sy + 12 * s, outline="#c7f0ff", width=1, tags="dynamic")

        bw = 26 * s
        self.canvas.create_rectangle(sx - bw, sy - 57 * s, sx + bw, sy - 53 * s, fill="#3d4044", outline="", tags="dynamic")
        hp_ratio = max(0.0, min(1.0, zombie.hp / (ZOMBIE_INFO[zombie.kind]["hp"] + 6)))
        self.canvas.create_rectangle(sx - bw, sy - 57 * s, sx - bw + bw * 2 * hp_ratio, sy - 53 * s, fill="#d14343", outline="", tags="dynamic")
        if ZOMBIE_INFO[zombie.kind]["armor"] > 0 and zombie.armor_hp > 0:
            ar = zombie.armor_hp / ZOMBIE_INFO[zombie.kind]["armor"]
            self.canvas.create_rectangle(sx - bw, sy - 52 * s, sx - bw + bw * 2 * ar, sy - 49 * s, fill="#9aa8b4", outline="", tags="dynamic")

    def _draw_projectile(self, p: Projectile, now: float) -> None:
        x = p.x
        y = self._cell_center_y(p.row) - 5
        sx, sy = self._world_to_screen(x, y)
        s = self._depth_scale(max(0.0, min(x, WORLD_W)))
        pulse = 1.0 + 0.08 * math.sin((now - p.born_ms) * 0.03)

        if p.kind in {"pea", "ice"}:
            r = (5.0 if p.kind == "pea" else 5.4) * s * pulse
            for i in range(1, 4):
                tx = x - p.speed * i * 1.6
                tsx, tsy = self._world_to_screen(tx, y)
                tr = r * (0.75 - i * 0.16)
                if tr > 0:
                    self.canvas.create_oval(tsx - tr, tsy - tr, tsx + tr, tsy + tr, fill=p.color, outline="", stipple="gray50", tags="dynamic")
            self.canvas.create_oval(sx - r, sy - r, sx + r, sy + r, fill=p.color, outline="#28502e", tags="dynamic")
            self.canvas.create_oval(sx - r * 0.35, sy - r * 0.35, sx + r * 0.1, sy + r * 0.1, fill="#f2fff2", outline="", tags="dynamic")
        else:
            r = 6.0 * s * pulse
            tail = max(6, min(18, int(abs(p.speed) * 2.4)))
            self.canvas.create_oval(sx - r, sy - r * 0.8, sx + r, sy + r * 0.8, fill="#8fc567", outline="#5f8847", tags="dynamic")
            self.canvas.create_line(sx + r * 0.2, sy, sx + r * 0.2 + tail, sy + 1.2, fill="#85b85f", width=3, tags="dynamic")

    def _draw_explosion(self, e: Explosion, now: float) -> None:
        dur = max(1.0, e.expires_ms - e.born_ms)
        p = max(0.0, min(1.0, (now - e.born_ms) / dur))
        radius = e.max_radius * (1.0 - (1.0 - p) ** 3)
        cx, cy = self._world_to_screen(e.x, self._cell_center_y(e.row))

        outer_w = max(1, int(6 * (1.0 - p) + 1))
        self.canvas.create_oval(
            cx - radius,
            cy - radius * 0.62,
            cx + radius,
            cy + radius * 0.62,
            outline="#ff912f",
            width=outer_w,
            tags="dynamic",
        )
        self.canvas.create_oval(
            cx - radius * 0.82,
            cy - radius * 0.52,
            cx + radius * 0.82,
            cy + radius * 0.52,
            outline="#ffbf5f",
            width=max(1, outer_w - 1),
            tags="dynamic",
        )
        self.canvas.create_oval(
            cx - radius * 0.58,
            cy - radius * 0.36,
            cx + radius * 0.58,
            cy + radius * 0.36,
            fill="#ffd06f",
            outline="",
            stipple="gray25",
            tags="dynamic",
        )
        self.canvas.create_oval(
            cx - radius * 0.36,
            cy - radius * 0.22,
            cx + radius * 0.36,
            cy + radius * 0.22,
            fill="#fff0b4",
            outline="",
            stipple="gray50",
            tags="dynamic",
        )

        star = radius * (0.18 + (1.0 - p) * 0.50)
        for i in range(6):
            a = i * (math.pi / 3) + p * 0.8
            self.canvas.create_line(
                cx + math.cos(a) * star * 0.35,
                cy + math.sin(a) * star * 0.24,
                cx + math.cos(a) * star * 1.2,
                cy + math.sin(a) * star * 0.86,
                fill="#ffb043",
                width=2,
                tags="dynamic",
            )
            self.canvas.create_line(
                cx + math.cos(a + 0.22) * star * 0.25,
                cy + math.sin(a + 0.22) * star * 0.18,
                cx + math.cos(a + 0.22) * star * 0.84,
                cy + math.sin(a + 0.22) * star * 0.6,
                fill="#ffd87a",
                width=1,
                tags="dynamic",
            )

    def _draw_particle(self, particle: Particle, now: float) -> None:
        life = max(1.0, particle.expires_ms - particle.born_ms)
        remain = max(0.0, min(1.0, (particle.expires_ms - now) / life))
        r = max(0.6, particle.size * remain)
        sx, sy = self._world_to_screen(particle.x, particle.y)
        self.canvas.create_oval(sx - r, sy - r, sx + r, sy + r, fill=particle.color, outline="", tags="dynamic")

    def _draw_mower(self, mower: Mower) -> None:
        sx, sy = self._world_to_screen(mower.x, mower.row * CELL_H + CELL_H * 0.56)
        s = self._depth_scale(max(0.0, mower.x))
        self.canvas.create_oval(sx - 19 * s, sy + 6 * s, sx + 19 * s, sy + 15 * s, fill="#3b434a", outline="", tags="dynamic")
        self.canvas.create_rectangle(sx - 19 * s, sy - 8 * s, sx + 19 * s, sy + 8 * s, fill="#c74d3f", outline="#6e231b", width=2, tags="dynamic")
        self.canvas.create_rectangle(sx - 6 * s, sy - 5 * s, sx + 11 * s, sy + 4 * s, fill="#d9d9d9", outline="", tags="dynamic")

    def _draw_dynamic(self, now: float) -> None:
        self.canvas.delete("dynamic")

        active_rows = {m.row for m in self.active_mowers}
        for row in range(ROWS):
            if self.mower_ready[row] and row not in active_rows:
                self._draw_mower(Mower(row=row, x=-24, speed=0))

        queue: list[tuple[float, str, object]] = []
        for plant in self.plants.values():
            queue.append((plant.row * 10000 + (WORLD_W - self._cell_center_x(plant.col)), "plant", plant))
        for zombie in self.zombies:
            if zombie.hp > 0:
                queue.append((zombie.row * 10000 + (WORLD_W - zombie.x) + 120, "zombie", zombie))
        for p in self.projectiles:
            queue.append((p.row * 10000 + (WORLD_W - p.x) + 70, "projectile", p))
        queue.sort(key=lambda x: x[0])

        for _, kind, obj in queue:
            if kind == "plant":
                self._draw_plant(obj, now)
            elif kind == "zombie":
                self._draw_zombie(obj, now)
            else:
                self._draw_projectile(obj, now)

        for mower in self.active_mowers:
            self._draw_mower(mower)
        for e in self.explosions:
            self._draw_explosion(e, now)
        for particle in self.particles:
            self._draw_particle(particle, now)

        if self.game_over:
            msg = "胜利" if self.game_win else "失败"
            self.canvas.create_rectangle(188, 188, CANVAS_W - 188, 304, fill="#000000", stipple="gray25", outline="", tags="dynamic")
            self.canvas.create_text(CANVAS_W / 2, 236, text=msg, fill="white", font=("Microsoft YaHei", 28, "bold"), tags="dynamic")
            self.canvas.create_text(CANVAS_W / 2, 272, text="点击“重新开始”再来一局", fill="#ececec", font=("Microsoft YaHei", 12), tags="dynamic")

    def _refresh_status(self) -> None:
        selected = "铲子" if self.selected == "shovel" else PLANT_INFO[self.selected]["name"]
        self.stage_name = self._current_level()[0]
        mowers = sum(1 for x in self.mower_ready if x)
        self.status_var.set(
            f"阳光 {self.sun:3d} | 选择 {selected} | 阶段 {self.stage_name} | 僵尸 {self.spawned:2d}/{self.max_zombies} | 推车 {mowers}"
        )

    def _end(self, win: bool) -> None:
        self.game_over = True
        self.game_win = win
        self.tip_var.set("所有波次已清除。" if win else "僵尸闯入了房子。")

    def _restart(self) -> None:
        self.sun = 225
        self.spawned = 0
        self.game_over = False
        self.game_win = False
        self.selected = "peashooter"
        self.plants.clear()
        self.zombies.clear()
        self.projectiles.clear()
        self.explosions.clear()
        self.particles.clear()
        self.active_mowers.clear()
        self.mower_ready = [True for _ in range(ROWS)]
        self.tip_var.set("新游戏开始。")
        self._reset_timers()
        self._refresh_card_highlight()
        self._refresh_status()
        self._draw_static_scene()
        self._draw_dynamic(self._now_ms())

    def _tick(self) -> None:
        now = self._now_ms()
        if not self.game_over:
            stage, level, spawn_range = self._current_level()
            self.stage_name = stage
            if self.sun < 340 and now >= self.next_passive_sun_ms:
                self.sun += 15
                self.next_passive_sun_ms = now + 9000
            if self.spawned < self.max_zombies and now >= self.next_spawn_ms:
                self._spawn_zombie()
                delay = random.randint(spawn_range[0], spawn_range[1])
                if level >= 3 and self.spawned % 9 == 0:
                    delay = max(900, int(delay * 0.74))
                    self.tip_var.set("小尸潮来袭。")
                self.next_spawn_ms = now + delay

            self._update_plants(now)
            self._update_projectiles(now)
            self._update_zombies(now)
            self._update_mowers(now)
            self._update_particles(now)
            self._cleanup_units(now)

            if self.spawned >= self.max_zombies and not self.zombies:
                self._end(True)

        self._refresh_status()
        self._draw_dynamic(now)
        self.root.after(40, self._tick)


def main() -> None:
    root = tk.Tk()
    MiniPvZ(root)
    root.mainloop()


if __name__ == "__main__":
    main()
