"""
wiz1_state.py - Wizardry 1 Memory State Parser
WhereAreWe(WAE) 소스 코드(Wiz1Memory.cs, Wiz1MemoryHacker.cs) 기반.

핵심 발견사항:
- WAE의 모든 주소 오프셋은 anchor 기준 (DOS 절대 주소가 아님)
- anchor = "WIZ1.DSK is missing" 문자열의 DOS 메모리 위치 (보통 0x01D5A)
- 실제 DOS 주소 = anchor + WAE_offset
- State1 = anchor + 2586  → 확인: Castle=21638, Edge=21518, Tavern=21678 ✅
- PartyInfo = anchor + 49010 = 0xDCCC  → 파티원 기록 시작 ✅
"""

import json
import os
import sys

from wiz_build_flags import RELEASE

RACES      = ["", "인간", "엘프", "드워프", "놈", "호빗"]
CLASSES    = ["전사", "마법사", "사제", "도적", "비숍", "사무라이", "로드", "닌자"]
STATUSES   = ["정상", "두려움", "수면", "마비", "석화", "사망", "재", "상실"]
ALIGNMENTS = ["선", "중립", "악"]
STAT_NAMES = ["STR", "I.Q.", "PIE", "VIT", "AGI", "LUC"]
# Screen phrase for a level-up drop. Same order as STAT_NAMES.
_LEVELUP_LOST = (
    "YOU LOST STRENGTH",
    "YOU LOST I.Q.",
    "YOU LOST PIETY",
    "YOU LOST VITALITY",
    "YOU LOST AGILITY",
    "YOU LOST LUCK",
)

# Byte 0x2C is shown left to right. Bit 1 is its high bit, bit 32 is the
# low bit of byte 0x2F. The six stats are not six adjacent 5-bit fields.
# 0x52 0x4A 0x52 0x4A is 18 in every stat. Bits 9 and 25 are unused.
_STAT_BITS = (
    (4, 5, 6, 7, 8),             # STR
    (15, 16, 1, 2, 3),           # I.Q.
    (10, 11, 12, 13, 14),        # PIE
    (20, 21, 22, 23, 24),        # VIT
    (31, 32, 17, 18, 19),        # AGI
    (26, 27, 28, 29, 30),        # LUC
)


def _stat_flag(raw, bitnum):
    index = bitnum - 1
    return (raw[index // 8] >> (7 - (index % 8))) & 1


def _put_stat_flag(raw, bitnum, flag):
    index = bitnum - 1
    shift = 7 - (index % 8)
    if flag:
        raw[index // 8] |= 1 << shift
    else:
        raw[index // 8] &= ~(1 << shift)


def unpack_stats(raw_int):
    """Read STR, I.Q., PIE, VIT, AGI, LUC from the 4 characteristic bytes."""
    raw = raw_int.to_bytes(4, "little")
    stats = []
    for bits in _STAT_BITS:
        value = 0
        for bitnum in bits:
            value = (value << 1) | _stat_flag(raw, bitnum)
        stats.append(value)
    return stats


def pack_stats(stats, base=0):
    """Write the six stats back. Unused bits stay as they were in base."""
    raw = bytearray(base.to_bytes(4, "little"))
    for value, bits in zip(stats, _STAT_BITS):
        for shift, bitnum in enumerate(bits):
            _put_stat_flag(raw, bitnum, (value >> (len(bits) - 1 - shift)) & 1)
    return bytes(raw)


assert unpack_stats(int.from_bytes(bytes.fromhex("524a524a"), "little")) == [18, 18, 18, 18, 18, 18]
assert pack_stats([18, 18, 18, 18, 18, 18]) == bytes.fromhex("524a524a")

# WAE MainSearch: "WIZ1.DSK is missing"
_MAIN_SEARCH = bytes([87,73,90,49,46,68,83,75,32,105,115,32,109,105,115,115,105,110,103])

# WAE Wiz1Memory.cs 오프셋 (anchor 기준)
_OFF_STATE1      = 2586
_OFF_STATE2      = 41864
_OFF_STATE3      = 38418
_OFF_STATE4      = 16268
_OFF_NUM_CHARS   = 48292   # anchor+48292 = 0xD9FE  (전체 캐릭터 수)
_OFF_PARTY_INFO  = 49010   # anchor+49010 = 0xDCCC  (파티원 레코드 시작)
# Wizardry 2, checked at the tavern against the party list on screen:
# count byte 6, and each 208-byte record's name, HP and DEAD matched.
_WIZ2_NUM_CHARS = 48458
_WIZ2_PARTY_INFO = 49176
# Wizardry 3 (WhereAreWe offsets, validated against WIZ3.COM):
_WIZ3_NUM_CHARS = 48624
_WIZ3_PARTY_INFO = 49362
_WIZ5_NUM_CHARS = 58896
_WIZ5_PARTY_INFO = 60930
_WIZ5_CHAR_SIZE = 246
_WIZ5_HPLEFT, _WIZ5_HPMAX = 102, 104
_OFF_FACING      = 48294
_OFF_LOC_DOWN    = 48296   # 현재 미궁 레벨

# 각 파티원 레코드 크기 (bytes)
_CHAR_RECORD_SIZE = 208
# Character record fields (Wizardry 1 TCHAR; 2-byte Pascal integers). The PC
# record matches it: stats 0x2C, gold 0x34, HP 0x86/0x88 and AC 0xB0 are the
# offsets this file already reads, and the record ends at 0xD0 = 208.
_OFF_STATUS = 0x28   # 0 OK, 1 AFRAID, 2 ASLEEP, 3 PLYZE, 4 STONED, 5 DEAD, 6 ASHES, 7 LOST
_OFF_HPLEFT = 0x86
_OFF_HPMAX = 0x88
_ST_DEAD, _ST_ASHES = 5, 6


def _decode_wiz_long(raw):
    """Decode Wizardry's five-byte, base-16 digit-pair integer."""
    if len(raw) < 5:
        return 0
    weights = ((16, 1), (4096, 256), (160000, 10000),
               (40960000, 2560000), (1600000000, 100000000))
    total = 0
    for value, (high_weight, low_weight) in zip(raw[:5], weights):
        total += (value >> 4) * high_weight
        total += (value & 0x0F) * low_weight
    return total

# WAE Wiz1MemoryHacker.GetMainState - state1 값 → (씬 이름, 설명)
STATE1_MAP = {
    21518: ("마을 외곽 (Edge of Town)",
            "[T] 훈련장 | [M] 미궁 | [C] 성 | [U] 유틸리티 | [L] 게임 종료"),
    21638: ("릴가민 성 (The Castle)",
            "모험가들의 거점 도시입니다.\n"
            "[G] 길가메시 선술집 | [A] 모험가 여관 | [T] 칸트 사원\n"
            "[B] 볼탁 상점 | [E] 마을 외곽"),
    21678: ("길가메시의 선술집 (Gilgamesh's Tavern)",
            "파티를 편성하고 인원을 관리하는 주점입니다.\n"
            "[A] 모험가 추가 | [R] 모험가 제외 | [1~6] 상태 점검 | [D] 골드 분배 | [L/↵] 성으로 복귀"),
    21780: ("선술집 - 모험가 제외 (Remove Char)",
            "파티에서 모험가를 제외합니다.\n제외할 모험가 번호를 입력하세요. | [L] 취소"),
    22602: ("선술집 - 모험가 추가 (Add Char)",
            "(문자) 선택 | ↵ 나가기"),
    22704: ("캐릭터 상세 점검 (Inspect)",
            "파티원의 능력치, 마법 슬롯, 소지품을 상세 점검합니다.\n"
            "[R] 읽기 | [T] 양도 | [P] 골드 모으기 | [L/↵] 복귀\n[E] 장착 | [D] 버리기 | [I] 감정"),
    23692: ("캐릭터 점검 - 주문서 읽기 (Inspect Read)", "[M] 마법사 주문서 | [P] 사제 주문서 | [↵] 복귀"),
    22696: ("캐릭터 점검 - 아이템 교환 (Inspect Trade)",
            "아이템 또는 골드를 다른 파티원에게 양도합니다.\n양도할 슬롯 번호를 선택하세요."),
    22234: ("모험가의 여관 (Adventurer's Inn)",
            "숙박하여 체력과 마법 슬롯을 회복합니다.\n"
            "[1~6] 숙박할 파티원 선택 후 객실 선택\n"
            "[A] 말구유 (무료) | [B] 간이침대 (10GP) | [C] 일반실 (50GP)\n"
            "[D] 상인 스위트 (200GP) | [E] 로열 스위트 (500GP) | [P] 골드 모으기 | [↵] 나가기"),
    22580: ("칸트 사원 (Temple of Cant)",
            "신성한 기도로 마비, 석화, 사망 상태를 치료하고 부활시킵니다.\n"
            "[A~Z] 치료할 대상 선택 | [↵] 성으로 복귀"),
    22310: ("볼탁 만물상점 (Boltac's Trading Post)",
            "무기, 방어구, 소모품을 거래하는 만물상입니다.\n"
            "[1~6] 파티원 선택 후 [B] 구매 | [S] 판매 | [U] 저주 해제\n"
            "[I] 감정 | [P] 골드 모으기 | [L/↵] 나가기"),
    21068: ("마을 외곽 - 유틸리티 (Utilities)", "[C] 이름 변경 | [M] 캐릭터 이동 | [P] 중단된 파티 재개 | [L] 나가기"),
    21114: ("마을 외곽 - 유틸리티 (Utilities)", "[C] 이름 변경 | [M] 캐릭터 이동 | [P] 중단된 파티 재개 | [L] 나가기"),
    21842: ("이름 변경 (Change Name)", ""),
    21076: ("디스크 교체 (Move Insert Disc)", ""),
    21850: ("캐릭터 선택 (Move Select Chars)", ""),
    21048: ("훈련장 (Training Grounds)",
            "캐릭터를 생성하고 전직, 명단을 관리하는 훈련장입니다.\n"
            "[C] 캐릭터 생성 | [I] 캐릭터 점검 | [R] 명단 열람 | [↵] 외곽으로 복귀"),
    21782: ("훈련장 - 캐릭터 선택 (Inspect Select Char)", "점검할 캐릭터 이름을 입력하세요."),
    21122: ("훈련장 - 캐릭터 선택됨 (Inspect Char Selected)", ""),
    22178: ("훈련장 - 캐릭터 점검 (Inspecting)",
            "캐릭터 능력치 확인 및 상위 직업으로 전직합니다.\n[C] 전직 | [L/↵] 나가기"),
    21154: ("훈련장 - 전직 (Change Class)",
            "상위 직업으로 전직합니다. 능력치를 초기화하므로 신중하게 선택하세요."),
    23166: ("훈련장 - 주문서 읽기 (Inspect Read)", "[M] 마법사 주문서 | [P] 사제 주문서 | [↵] 복귀"),
    21082: ("캐릭터 작성 - 이름 입력 (Create Select Name)", "새 캐릭터의 이름을 입력하세요."),
    21126: ("캐릭터 작성 - 종족 선택 (Create Select Race)",
            "종족을 선택하세요: Human / Elf / Dwarf / Gnome / Hobbit"),
    21078: ("캐릭터 작성 - 성향 선택 (Create Select Alignment)",
            "성향을 선택하세요: Good / Neutral / Evil"),
    20888: ("캐릭터 명단 (Roster of Characters)",
            "성 및 훈련장에 등록된 전체 캐릭터 명단입니다.\n아무 키나 누르면 복귀합니다."),
    21474: ("캠프 (Camp)",
            "던전 내 안전지대에서 파티를 정비합니다.\n"
            "[C] 치료/탐색 주문 | [R] 대열 변경 | [I] 캐릭터 점검 | [L/↵] 미궁 복귀"),
    22534: ("캠프 - 캐릭터 점검 (Camp Inspecting)",
            "파티원의 장비와 인벤토리를 점검합니다.\n[E] 장착/해제 | [D] 폐기 | [T] 양도 | [L/↵] 캠프 복귀"),
    22700: ("캠프 - 캐릭터 점검 (Camp Inspecting)",
            "파티원의 장비와 인벤토리를 점검합니다.\n[E] 장착/해제 | [D] 폐기 | [T] 양도 | [L/↵] 캠프 복귀"),
    23688: ("캠프 점검 - 주문서 읽기 (Camp Inspect Read)", "[M] 마법사 주문서 | [P] 사제 주문서 | [↵] 복귀"),
    21746: ("캠프 - 대열 변경 (Camp Reorder)",
            "파티 대열을 재배치합니다 (1~3번 전열, 4~6번 후열)."),
    21470: ("캠프 - 장비 장착 (Camp Equip)", "파티원의 장비를 장착하거나 해제합니다."),
    21616: ("미궁 탐색 (In the Maze)",
            "광왕 트레보의 미궁을 탐험하고 있습니다.\n"
            "[W] 전진 | [A] 좌회전 | [D] 우회전 | [S] 상태창 | [C] 캠프 | [I] 조사 | [O] 대기"),
    21840: ("미궁 탐색 (In the Maze)",
            "광왕 트레보의 미궁을 탐험하고 있습니다.\n"
            "[W] 전진 | [A] 좌회전 | [D] 우회전 | [S] 상태창 | [C] 캠프 | [I] 조사 | [O] 대기"),
    21560: ("전투 준비 (Pre-Combat)", "적과 조우했습니다!"),
    10190: ("타이틀 화면 (Title Screen)",
            "위저드리 1: 광왕의 시련장에 오신 것을 환영합니다!\n[S] 게임 시작 | [M] 시나리오 디스크 생성"),
    20812: ("디스크 삽입 요청 (Insert Disk)", ""),
}


class Wizardry1State:
    def __init__(self, hook, ko_data_path=None):
        self.hook = hook
        if not ko_data_path:
            base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            ko_data_path = os.path.join(base, 'wiz1_ko_data.json')

        self.ko_data = {}
        try:
            if os.path.exists(ko_data_path):
                with open(ko_data_path, 'r', encoding='utf-8') as f:
                    self.ko_data = json.load(f)
        except Exception:
            pass

        self.current_scene = "게임 시작 대기 중..."
        self.scene_desc = ""
        self.state1 = 0
        self.state2 = 0
        self.state3 = 0
        self.state4 = 0
        self.party = []
        self.monsters = []
        self.active_messages = []
        self.active_spells = []
        # 스탯 하락 버그 방지 가디언 속성
        self.prevent_stat_loss = True
        self.last_char_state = {}
        self.stat_protection_logs = []
        self.levelup_protected = set()
        # anchor: "WIZ1.DSK is missing" 문자열 위치 (캐시)
        self._anchor = None
        self._wiz2_anchor = None
        self._wiz2_state1 = 0
        self._wiz3_anchor = None
        self._wiz3_state1 = 0
        self._wiz4_anchor = None
        self._wiz5_anchor = None
        self.game = None
        # Legacy compat
        self.curseg = 0
        self.curproc = 0

    def _r16(self, mem, addr):
        if addr + 2 > len(mem):
            return 0
        return int.from_bytes(mem[addr:addr + 2], 'little')

    def _r16s(self, mem, addr):
        if addr + 2 > len(mem):
            return 0
        v = int.from_bytes(mem[addr:addr + 2], 'little')
        return v if v < 32768 else v - 65536

    def update(self):
        """DOSBox 메모리를 폴링하여 현재 게임 상태를 갱신합니다."""
        if not self.hook.is_alive():
            self.current_scene = "DOSBox 미연결 (게임을 실행해 주세요)"
            self.scene_desc = ""
            self.state1 = self.state2 = self.state3 = self.state4 = 0
            self._anchor = None
            self._wiz2_anchor = None
            self._wiz2_state1 = 0
            self._wiz3_anchor = None
            self._wiz3_state1 = 0
            self._wiz4_anchor = None
            self._wiz5_anchor = None
            self.game = None
            self.party.clear()
            self.monsters.clear()
            self.active_messages.clear()
            self.active_spells.clear()
            self.last_char_state.clear()
            self.levelup_protected.clear()
            self.stat_protection_logs.clear()
            return False

        # State2(0xC0E2), NumChars(0xD9FE), PartyInfo(0xDCCC) 등을 포함한다.
        # PartyInfo에는 최대 6개의 208-byte 레코드가 이어진다. anchor가
        # 0x1D5A일 때 마지막 레코드의 끝은 0xE1AC이므로, 0xE000까지만
        # 읽으면 앞의 3명만 온전히 읽히고 4~6번은 범위 밖이 된다.
        mem = self.hook.read_bytes(0x0000, 0xF000)
        found1 = mem.find(_MAIN_SEARCH) if mem and len(mem) >= 0x4000 else -1
        found2 = mem.find(b'WIZ2.DSK is missing') if mem and len(mem) >= 0x4000 else -1
        found3 = mem.find(b'WIZ3.DSK is missing') if mem and len(mem) >= 0x4000 else -1
        found4 = mem.find(b'WIZ4.DSK is missing') if mem and len(mem) >= 0x4000 else -1
        found5 = mem.find(b'WIZ5.DSK is missing') if mem and len(mem) >= 0x4000 else -1
        game = 5 if found5 >= 0 else (4 if found4 >= 0 else (3 if found3 >= 0 and found1 < 0 and found2 < 0 else (2 if found2 >= 0 and found1 < 0 and found3 < 0 else (1 if found1 >= 0 and found2 < 0 and found3 < 0 else None))))
        if not game:
            self.game = None
            self._anchor = None
            self._wiz2_anchor = None
            self._wiz2_state1 = 0
            self._wiz3_anchor = None
            self._wiz3_state1 = 0
            self._wiz5_anchor = None
            self.state1 = self.state2 = self.state3 = self.state4 = 0
            self.party.clear()
            self.monsters.clear()
            self.active_messages.clear()
            self.active_spells.clear()
            self.last_char_state.clear()
            self.levelup_protected.clear()
            self.stat_protection_logs.clear()
            self.current_scene = "게임 시작 대기 중..."
            self.scene_desc = "위저드리 실행을 기다리고 있습니다."
            return False

        if game != self.game:
            self.party.clear()
            self.last_char_state.clear()
            self.levelup_protected.clear()
            self.stat_protection_logs.clear()
        if game != 5:
            self._wiz5_anchor = None

        if game in (4, 5):
            self.game = game
            self._anchor = None
            self._wiz4_anchor = found4 if game == 4 else None
            self._wiz5_anchor = found5 if game == 5 else None
            self._wiz2_anchor = None
            self._wiz2_state1 = 0
            self._wiz3_anchor = None
            self._wiz3_state1 = 0
            self.state1 = self.state2 = self.state3 = self.state4 = 0
            self.monsters.clear()
            self.active_messages.clear()
            self.active_spells.clear()
            self.current_scene = f"위저드리 {game}"
            self.scene_desc = "베르드나의 귀환" if game == 4 else "재앙의 심장"
            self.party.clear()
            return True

        if game == 3:
            self.game = 3
            self._anchor = None
            self._wiz2_anchor = None
            self._wiz2_state1 = 0
            self._wiz3_anchor = found3
            self._wiz3_state1 = self._r16(mem, found3 + 2938)
            self.state1 = self.state2 = self.state3 = self.state4 = 0
            self.monsters.clear()
            self.active_messages.clear()
            self.active_spells.clear()
            self.current_scene = "위저드리 3"
            self.scene_desc = ""
            self._parse_party(mem)
            return True

        if game == 2:
            self.game = 2
            self._anchor = None
            self._wiz2_anchor = found2
            self._wiz2_state1 = self._r16(mem, found2 + 2762)
            self._wiz3_anchor = None
            self._wiz3_state1 = 0
            self.state1 = self.state2 = self.state3 = self.state4 = 0
            self.monsters.clear()
            self.active_messages.clear()
            self.active_spells.clear()
            self.current_scene = "위저드리 2"
            self.scene_desc = ""
            self._parse_party(mem)
            return True

        self.game = 1
        self._anchor = found1
        self._wiz2_anchor = None
        self._wiz2_state1 = 0
        self._wiz3_anchor = None
        self._wiz3_state1 = 0

        self._parse_scene(mem)
        self._parse_party(mem)
        self._parse_combat(mem)
        self._parse_active_messages(mem)
        return True

    def _parse_scene(self, mem):
        """
        WAE Wiz1MemoryHacker.GetMainState 로직 이식.
        실제 DOS 주소 = anchor + WAE_offset
        """
        a = self._anchor
        self.state1 = self._r16(mem, a + _OFF_STATE1)
        self.state2 = self._r16(mem, a + _OFF_STATE2)
        self.state3 = self._r16(mem, a + _OFF_STATE3)
        self.state4 = self._r16(mem, a + _OFF_STATE4)

        if self.state1 == 0:
            self.current_scene = "게임 시작 대기 중..."
            self.scene_desc = "위저드리 1 실행을 기다리고 있습니다."
            return

        # --- 복합 분기 케이스 ---

        # 보물상자
        if self.state1 == 21676:
            if self.state4 == 17666:
                self.current_scene = "보물상자 - 누가 열겠습니까? (Who Will Open)"
            elif self.state4 == 7874:
                self.current_scene = "보물상자 - 칼포 주문 투시 (Who Will Calfo)"
            elif self.state4 == 13382:
                self.current_scene = "보물상자 - 함정 조사 (Who Will Inspect)"
            elif self.state4 == 12158:
                if self.state2 == 56498:
                    self.current_scene = "보물상자 - 해제 실패 (Could Not Disarm)"
                elif self.state2 == 47334:
                    self.current_scene = "보물상자 - 함정 종류 입력 (Enter Trap Type)"
                elif self.state2 == 22816:
                    self.current_scene = "전투 승리 - 보물상자 (Treasure Chest)"
                else:
                    self.current_scene = "보물상자 - 함정 해제 (Who Will Disarm)"
            else:
                self.current_scene = "전투 승리 - 보물상자 (Treasure Chest)"
            self.scene_desc = "몬스터를 물리치고 보물상자를 발견했습니다! 함정을 조심하십시오.\n[O] 즉시 개봉 | [I] 함정 조사 | [C] 칼포 주문 | [D] 함정 해제 | [L] 포기"
            return

        # 전투
        if self.state1 in (21962, 22296):
            if self.state3 == 63486:
                self.current_scene = "전투 - 행동 선택 (Combat Options)"
            elif self.state3 in (193, 3345):
                self.current_scene = "전투 - 타겟 지정 (Select Fight Target)"
            elif self.state3 == 47228:
                self.current_scene = "전투 - 마법 선택 (Combat Select Spell)"
            elif self.state3 == 37400:
                self.current_scene = "전투 - 라운드 확정 (Confirm Round)"
            elif self.state3 == 14596:
                self.current_scene = "전투 - 우호적 만남 (Friendly)"
            else:
                self.current_scene = "전투 돌입! (Combat)"
            self.scene_desc = ("적 몬스터 무리와 교전 중입니다!\n"
                               "전열(1~3): [F] 공격 | [P] 방어 | [C] 주문 | [U] 도구 | [D] 퇴마 | [R] 도주\n"
                               "후열(4~6): [P] 방어 | [C] 주문 | [U] 도구 | [D] 퇴마 | [R] 도주")
            return

        # 전투 중 아이템/주문
        if self.state1 == 22692:
            if self.state2 == 7:
                self.current_scene = "전투 - 아이템 사용 선택 (Use Select Item)"
            elif self.state2 == 3:
                self.current_scene = "전투 - 아이템 버리기 (Drop Select Item)"
            elif self.state2 == 6:
                self.current_scene = "전투 - 주문 선택 (Select Spell)"
            else:
                self.current_scene = "전투 - 행동 처리 중 (Cast/Drop/Use)"
            self.scene_desc = ""
            return

        # 전투 승리 / 캐릭터 생성
        if self.state1 == 21448:
            if self.state3 == 37400:
                self.current_scene = "전투 승리 - 경험치 획득 (Receive EXP)"
                self.scene_desc = "전투에서 승리했습니다! 경험치를 획득합니다."
            elif self.state2 == 40838:
                self.current_scene = "캐릭터 작성 - 캐릭터 저장 (Keep Char)"
                self.scene_desc = "새 캐릭터를 저장하겠습니까? (Y/N)"
            else:
                self.current_scene = "캐릭터 작성 - 능력치 교환 (Exchange Stat)"
                self.scene_desc = "주사위 보너스 포인트를 능력치에 배분합니다.\nSTR / I.Q. / PIE / VIT / AGI / LUC 순서로 입력합니다."
            return

        # 캐릭터 작성 이름/암호
        if self.state1 == 21082:
            if self.state2 == 53733:
                self.current_scene = "캐릭터 작성 - 암호 입력 (Create Select Password)"
                self.scene_desc = "캐릭터 보호용 암호를 입력하세요."
            else:
                self.current_scene = "캐릭터 작성 - 이름 입력 (Create Select Name)"
                self.scene_desc = "새 캐릭터의 이름을 입력하세요 (최대 15자)."
            return

        # --- 단순 state1 매핑 ---
        if self.state1 in STATE1_MAP:
            name, desc = STATE1_MAP[self.state1]
            self.current_scene = name
            self.scene_desc = desc
            return

        # 폴백
        self.current_scene = f"알 수 없는 상태 (state1={self.state1})"
        self.scene_desc = ""

    def _party_records(self, notes=None):
        """(address, name, status, hp, hp_max) for each party member.

        Returns nothing unless every record looks like a character, so a
        wrong anchor never leads to a write. ``notes`` (a list) collects
        what was read and why a check failed, for wiz_party_debug.log.
        """
        notes = notes if notes is not None else []
        if self.game == 5 and self._wiz5_anchor is not None:
            anchor, num_off, party_off = self._wiz5_anchor, _WIZ5_NUM_CHARS, _WIZ5_PARTY_INFO
        elif self.game == 3 and self._wiz3_anchor is not None:
            anchor, num_off, party_off = self._wiz3_anchor, _WIZ3_NUM_CHARS, _WIZ3_PARTY_INFO
        elif self.game == 2 and self._wiz2_anchor is not None:
            anchor, num_off, party_off = self._wiz2_anchor, _WIZ2_NUM_CHARS, _WIZ2_PARTY_INFO
        elif self.game == 1 and self._anchor is not None:
            anchor, num_off, party_off = self._anchor, _OFF_NUM_CHARS, _OFF_PARTY_INFO
        else:
            notes.append("anchor: none")
            return []
        notes.append(f"anchor: {anchor:#06x}  state1: {self.state1}")
        count = self.hook.read_bytes(anchor + num_off, 2)
        n = count[0] if count else 0
        notes.append(f"party count (+{num_off}): {count.hex() if count else None}")
        if not 1 <= n <= 6:
            notes.append("FAIL: party count not 1-6")
            return []
        out = []
        size = _WIZ5_CHAR_SIZE if self.game == 5 else _CHAR_RECORD_SIZE
        hp_off, max_off = (_WIZ5_HPLEFT, _WIZ5_HPMAX) if self.game == 5 else (_OFF_HPLEFT, _OFF_HPMAX)
        for i in range(n):
            addr = anchor + party_off + i * size
            raw = self.hook.read_bytes(addr, size)
            if not raw or len(raw) < size:
                notes.append(f"#{i} {addr:#06x}: read failed")
                return []
            for row in range(0, size, 16):
                notes.append(f"#{i} +{row:02x}: {raw[row:row + 16].hex(' ')}")
            nlen = raw[0]
            if not 1 <= nlen <= 15 or not all(32 <= b < 127 for b in raw[1:1 + nlen]):
                notes.append(f"FAIL #{i}: name")
                return []
            status = int.from_bytes(raw[_OFF_STATUS:_OFF_STATUS + 2], 'little')
            # HPLEFT is a signed Pascal integer; a dead character can be below 0.
            hp = int.from_bytes(raw[hp_off:hp_off + 2], 'little', signed=True)
            hp_max = int.from_bytes(raw[max_off:max_off + 2], 'little')
            name = raw[1:1 + nlen].decode('latin1')
            notes.append(f"#{i} {name}: status {status} hp {hp}/{hp_max}")
            # The party list shows four digits, up to 9999.
            if status > 7 or not 1 <= hp_max <= 9999 or not -9999 <= hp <= 9999:
                notes.append(f"FAIL #{i}: status/hp out of range")
                return []
            out.append((addr, name, status, hp, hp_max))
        return out

    def heal_party(self, notes=None):
        """Set HP to max for living members. Returns the names healed."""
        healed = []
        hp_off = _WIZ5_HPLEFT if self.game == 5 else _OFF_HPLEFT
        for addr, name, status, hp, hp_max in self._party_records(notes):
            if status >= _ST_DEAD or hp >= hp_max:
                continue
            if self.hook.write_bytes(addr + hp_off, hp_max.to_bytes(2, 'little')):
                healed.append(name)
        return healed

    def revive_party(self, notes=None):
        """Bring DEAD or ASHES members back OK with full HP. Returns the names."""
        revived = []
        hp_off = _WIZ5_HPLEFT if self.game == 5 else _OFF_HPLEFT
        for addr, name, status, hp, hp_max in self._party_records(notes):
            if status not in (_ST_DEAD, _ST_ASHES):
                continue
            if (self.hook.write_bytes(addr + hp_off, hp_max.to_bytes(2, 'little'))
                    and self.hook.write_bytes(addr + _OFF_STATUS, (0).to_bytes(2, 'little'))):
                revived.append(name)
        return revived

    def identify_party(self, notes=None):
        """Mark every unidentified item the party carries as identified.

        Wizardry 1-3 record: POSSCNT at +0x3A, then 8 entries of 8 bytes from
        +0x3C (EQUIPED, CURSED, IDENTIFIED, EQINDEX, 16 bits each; checked
        against the screen of the live party). Only IDENTIFIED is written.
        Returns the names with something identified.
        """
        if self.game == 5:
            return self._identify_party_wiz5(notes)
        if self.game not in (1, 2, 3):
            return []
        done = []
        for addr, name, status, hp, hp_max in self._party_records(notes):
            head = self.hook.read_bytes(addr + 0x3A, 66)
            if not head or len(head) < 66:
                continue
            count = int.from_bytes(head[0:2], 'little')
            if not 1 <= count <= 8:
                continue
            changed = 0
            for i in range(count):
                entry = head[2 + 8 * i: 10 + 8 * i]
                identified = int.from_bytes(entry[4:6], 'little')
                if identified == 0 and int.from_bytes(entry[6:8], 'little') != 0:
                    if self.hook.write_bytes(addr + 0x3C + 8 * i + 4, (1).to_bytes(2, 'little')):
                        changed += 1
            if changed:
                done.append(name)
        return done

    def _identify_party_wiz5(self, notes=None):
        """Wizardry 5 record (246 bytes): POSSCNT at +0x3A, then 4-byte entries
        from +0x3C (item number, flag word). Flag bit 1 is identified, bit 2
        cursed: the shop's "THAT HAS BEEN IDENTIFIED" / "NOT A CURSED ITEM"
        tests (SHOPS proc 27) and the bishop's identify (CAMP proc 53).
        Only bit 1 is set."""
        done = []
        for addr, name, status, hp, hp_max in self._party_records(notes):
            head = self.hook.read_bytes(addr + 0x3A, 2 + 4 * 8)
            if not head or len(head) < 34:
                continue
            count = int.from_bytes(head[0:2], 'little')
            if not 1 <= count <= 8:
                continue
            changed = 0
            for i in range(count):
                item = int.from_bytes(head[2 + 4 * i:4 + 4 * i], 'little')
                flags = int.from_bytes(head[4 + 4 * i:6 + 4 * i], 'little')
                if item and not flags & 2:
                    if self.hook.write_bytes(addr + 0x3C + 4 * i + 2, (flags | 2).to_bytes(2, 'little')):
                        changed += 1
            if changed:
                done.append(name)
        return done

    def _parse_party(self, mem):
        """파티원 정보 파싱.

        WhereAreWe의 ``Wiz1Memory``에서 NumChars와 PartyInfo는 각각 독립된
        주소이다.  PartyInfo 앞의 워드는 파티 인원 수가 아니다.
        """
        self.party = []
        if self.game == 3 and self._wiz3_anchor is not None:
            anchor = self._wiz3_anchor
            party_base = anchor + _WIZ3_PARTY_INFO
            num_addr = anchor + _WIZ3_NUM_CHARS
        elif self.game == 2 and self._wiz2_anchor is not None:
            anchor = self._wiz2_anchor
            party_base = anchor + _WIZ2_PARTY_INFO
            num_addr = anchor + _WIZ2_NUM_CHARS
        elif self.game == 1 and self._anchor is not None:
            anchor = self._anchor
            party_base = anchor + _OFF_PARTY_INFO
            num_addr = anchor + _OFF_NUM_CHARS
        else:
            return
        num_party = mem[num_addr] if 0 <= num_addr < len(mem) else 0
        if not (1 <= num_party <= 6):
            return

        for i in range(num_party):
            rec_addr = party_base + i * _CHAR_RECORD_SIZE
            if rec_addr + _CHAR_RECORD_SIZE > len(mem):
                break
            raw = mem[rec_addr: rec_addr + _CHAR_RECORD_SIZE]

            # Wiz1's in-memory party record begins with a Pascal string
            # (one-byte length followed by up to 15 Latin-1 characters).
            nlen = raw[0]
            if not (1 <= nlen <= 15):
                continue
            try:
                name = raw[1: 1 + nlen].decode('latin1').strip()
            except Exception:
                continue
            if not name:
                continue

            align   = raw[0x20] if 0x20 < len(raw) else 0
            race    = raw[0x22] if 0x22 < len(raw) else 0
            p_class = raw[0x24] if 0x24 < len(raw) else 0
            level   = int.from_bytes(raw[0x82:0x84], 'little') if 0x84 <= len(raw) else 0
            hp      = int.from_bytes(raw[0x86:0x88], 'little') if 0x88 <= len(raw) else 0
            max_hp  = int.from_bytes(raw[0x88:0x8A], 'little') if 0x8A <= len(raw) else 0
            gold    = _decode_wiz_long(raw[0x34:0x39])
            ac      = int.from_bytes(raw[0xB0:0xB2], 'little', signed=True) if 0xB2 <= len(raw) else 0
            status_idx = raw[0x8A] if 0x8A < len(raw) else 0
            status_str = STATUSES[status_idx] if 0 <= status_idx < len(STATUSES) else "정상"
            # Stats (STR, IQ, PIE, VIT, AGI, LUC) - 4 bytes at offset 0x2C (5-bit packed)
            raw_stats = int.from_bytes(raw[0x2C:0x30], 'little') if 0x30 <= len(raw) else 0
            stats = unpack_stats(raw_stats)

            # 레벨업 스탯 감소 방지 / 보정 로직
            if self.prevent_stat_loss and name in self.last_char_state:
                prev_data = self.last_char_state[name]
                prev_level = prev_data.get("level", 0)
                prev_stats = prev_data.get("stats", [])

                if level == prev_level and prev_level > 0 and len(prev_stats) == 6:
                    # The level byte can move a poll before the stat bytes.
                    keys = [
                        _LEVELUP_LOST[i]
                        for i in range(6)
                        if stats[i] < prev_stats[i]
                    ]
                    if keys:
                        adjusted = [max(old_v, new_v) for old_v, new_v in zip(prev_stats, stats)]
                        self.hook.write_bytes(rec_addr + 0x2C, pack_stats(adjusted, raw_stats))
                        stats = adjusted
                        self.levelup_protected = set(keys)
                elif level > prev_level and prev_level > 0 and len(prev_stats) == 6:
                    need_fix = False
                    adjusted = list(stats)
                    changes = []
                    protected_keys = []
                    for s_idx in range(6):
                        old_v = prev_stats[s_idx]
                        new_v = stats[s_idx]
                        s_name = STAT_NAMES[s_idx]
                        if new_v < old_v:
                            adjusted[s_idx] = old_v
                            need_fix = True
                            protected_keys.append(_LEVELUP_LOST[s_idx])
                            changes.append(f"{s_name}: {new_v}→{old_v}(보호)")
                        elif new_v > old_v:
                            changes.append(f"{s_name}: {old_v}→{new_v}(+1)")
                    self.levelup_protected = set(protected_keys)

                    if need_fix:
                        packed_bytes = pack_stats(adjusted, raw_stats)
                        self.hook.write_bytes(rec_addr + 0x2C, packed_bytes)
                        stats = adjusted
                        log_msg = f"[스탯 보호] {name} (LV {prev_level}→{level}) " + ", ".join(changes)
                        self.stat_protection_logs.append(log_msg)
                        if len(self.stat_protection_logs) > 5:
                            self.stat_protection_logs.pop(0)
                        if sys.stdout is not None:
                            print(f"[Wiz{self.game} Companion] {log_msg}")
                    elif changes:
                        log_msg = f"[레벨업] {name} (LV {prev_level}→{level}) " + ", ".join(changes)
                        self.stat_protection_logs.append(log_msg)
                        if len(self.stat_protection_logs) > 5:
                            self.stat_protection_logs.pop(0)
                        if sys.stdout is not None:
                            print(f"[Wiz{self.game} Companion] {log_msg}")
            elif name in self.last_char_state:
                prev_level = self.last_char_state[name].get("level", 0)
                if level > prev_level > 0:
                    self.levelup_protected = set()

            self.last_char_state[name] = {"level": level, "stats": stats}

            self.party.append({
                "name":    name,
                "align":   ALIGNMENTS[align]   if 0 <= align   < len(ALIGNMENTS) else "",
                "race":    RACES[race]          if 0 <= race    < len(RACES)      else "",
                "class":   CLASSES[p_class]     if 0 <= p_class < len(CLASSES)    else "",
                "level":   level,
                "hp":      hp,
                "max_hp":  max_hp,
                "gold":    gold,
                "ac":      ac,
                "status":  status_str,
                "stats":   stats,
            })

    def _log_monster_names(self, mem, name):
        """Read-only: keep the Pascal strings around a monster name in memory.

        The PC game files hold monster names packed, so the unidentified
        names ("KIMONOED MAN") are collected here as they are met in
        combat, into monster_seen.log in the logs folder.
        """
        if RELEASE:
            return
        seen = self.__dict__.setdefault('_monster_logged', set())
        if name in seen:
            return
        seen.add(name)
        pos = mem.find(name.encode('latin1'))
        if pos < 0:
            return
        lo, hi = max(0, pos - 96), min(len(mem), pos + 96)
        found = []
        o = lo
        while o < hi:
            n = mem[o]
            text = mem[o + 1:o + 1 + n]
            if 2 <= n <= 15 and len(text) == n and all(48 <= b <= 90 or b in b" '-." for b in text):
                found.append((o - pos, text.decode('latin1')))
                o += 1 + n
            else:
                o += 1
        try:
            from cga_text_extractor import dev_path
            with open(dev_path('logs', 'monster_seen.log'), 'a', encoding='utf-8') as handle:
                handle.write(f"{name}\t{found}\t{mem[lo:hi].hex()}\n")
        except Exception:
            pass

    def _parse_combat(self, mem):
        self.monsters = []
        if "전투" not in self.current_scene:
            return
        for m_name, m_info in self.ko_data.get("monsters", {}).items():
            try:
                if m_name.encode('latin1') in mem:
                    self._log_monster_names(mem, m_name)
                    self.monsters.append({
                        "en":     m_name,
                        "ko":     m_info.get("ko", m_name),
                        "desc":   m_info.get("desc", ""),
                        "danger": m_info.get("danger", ""),
                    })
            except Exception:
                pass

    def _parse_active_messages(self, mem):
        self.active_spells = []
        for s_name, s_info in self.ko_data.get("spells", {}).items():
            try:
                tag = f" {s_name} ".encode('latin1')
                if tag in mem:
                    self.active_spells.append({
                        "en":    s_name,
                        "ko":    s_info.get("ko", s_name),
                        "class": s_info.get("class", ""),
                        "level": s_info.get("level", 0),
                        "desc":  s_info.get("desc", ""),
                    })
            except Exception:
                pass
