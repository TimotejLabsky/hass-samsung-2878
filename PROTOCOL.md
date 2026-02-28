# Samsung AC14K XML Protocol Reference

Reverse-engineered from Samsung Smart Air Conditioner APK (com.samsung.rac v1.2.94, "Jungfrau" variant).
Tested and confirmed working with AR12HSFSAWKN (FW 01538A140403).

## Confirmed Device Details

- **Model**: AR12HSFSAWKN (AC14K / Jungfrau)
- **DUID**: Derived from MAC address (strip colons)
- **Port**: 2878
- **SW Version**: 01538A140403, Panel 150224, Outdoor 130709

## Connection

- **Port 2878** — TLS control/command (bidirectional) ✅ CONFIRMED
- **Port 2848** — TLS status/notification (read-only, push updates)
- **TLS**: v1.0, AES256-SHA cipher, mutual TLS with `ac14k_m.pem` client cert
- **Protocol**: Line-based (each message is one line, `\r\n` terminated)
- **Framing**: On connect, AC sends `DPLUG-1.6` then `<?xml ...><Update Type="InvalidateAccount" .../>`
- **Node.js**: Requires v16+ with `--tls-min-v1.0` flag
- **SSID**: Must NOT be hidden (Espressif WiFi module cannot find hidden SSIDs)

## Protocol Flow

### AP Mode (WiFi Provisioning)
```
1. Connect to AC's WiFi AP (192.168.1.254)
2. TLS connect to port 2878
3. Receive: DPLUG-1.6
4. Receive: <Update Type="InvalidateAccount" Status="Okay" />
5. Send: APConnectionConfig with home WiFi credentials
6. AC joins home WiFi, AP mode ends
```

### Normal Mode (Home WiFi) ✅ CONFIRMED
```
1. Discover AC via SSDP or subnet scan (scan-subnet.js)
2. TLS connect to port 2878
3. Receive: DPLUG-1.6
4. Receive: <Update Type="InvalidateAccount" .../>
5. Send: <Request Type="GetToken"></Request>
6. Receive: <Response Type="GetToken" Status="Ready"/>
7. Power-cycle AC with remote (OFF, wait 5s, ON)
8. Receive: <Update Type="GetToken" Status="Completed" Token="YOUR_TOKEN"/>
9. Save token, use AuthToken for subsequent sessions
```

### Authenticated Session ✅ CONFIRMED
```
1. TLS connect to AC_IP:2878
2. Receive: DPLUG-1.6 + InvalidateAccount
3. Send: <Request Type="AuthToken"><User Token="..." /></Request>
4. Receive: <Response Type="AuthToken" Status="Okay" StartFrom="..." />
5. Send: DeviceState (DUID=YOUR_DUID), DeviceControl, etc.
6. Receive push status updates (AC_FUN_POWER, AC_SG_INTERNET, etc.)
```

---

## Request XML Formats

### GetToken
```xml
<Request Type="GetToken"></Request>
```
Note: Only works on home WiFi, NOT in AP mode. AC will close connection if sent in AP mode.

### AuthToken
```xml
<Request Type="AuthToken">
  <User Token="SAVED_TOKEN_HERE" />
</Request>
```

### Authenticate (Legacy)
```xml
<Request Type="Authenticate">
  <User Password="PASSWORD" />
</Request>
```

### APConnectionConfig (WiFi Provisioning)
```xml
<Request Type="APConnectionConfig">
  <ConnectionConfig SSID="MyNetwork" AuthMode="WPA2" EncryptType="AES" Key1="MyPassword" />
</Request>
```

AuthMode values: `OPEN`, `WEP`, `WPA`, `WPA2`
EncryptType values: `TKIP`, `AES` (only for WPA/WPA2)
Key1 omitted when AuthMode=OPEN, only Key1 (no EncryptType) for WEP.

### DeviceState
```xml
<Request Type="DeviceState" DUID="DEVICE_UUID"></Request>
```

### DeviceControl (Jungfrau variant — AC14K uses this)
```xml
<Request Type="DeviceControl">
  <Control CommandID="cmd00000" DUID="DEVICE_UUID">
    <Attr ID="AC_FUN_POWER" Value="On" />
  </Control>
</Request>
```

The Jungfrau variant builds XML via string concatenation using the template
`<Attr ID="#1#" Value="#2#" />` where `#1#` and `#2#` are replaced with the
attribute name and value. Multiple `<Attr>` elements can be included.

### DeviceControl (Venice variant — older devices)
```xml
<Request Type="DeviceControl">
  <Control CommandID="cmd00000" DUID="DEVICE_UUID">
    <Attr ID="AC_FUNCTION_POWER" Value="On" />
    <Attr ID="AC_FUNCTION_OPMODE" Value="Cool" />
    <Attr ID="AC_FUNCTION_TEMPSET" Value="24" />
  </Control>
</Request>
```
Note: Venice uses `AC_FUNCTION_*` names, Jungfrau uses `AC_FUN_*` names.

Common Jungfrau attributes:

| Attr ID | Values | Description |
|---------|--------|-------------|
| AC_FUN_POWER | On, Off | Power on/off |
| AC_FUN_OPMODE | Auto, Cool, Dry, Wind, Heat | Operation mode |
| AC_FUN_TEMPSET | 16-30 (integer) | Target temperature |
| AC_FUN_WINDLEVEL | Auto, Low, Mid, High, Turbo | Fan speed |
| AC_FUN_DIRECTION | Off, Indirect, Direct, Center, Wide, Left, Right, Long, SwingUD, SwingLR, Rotation, Fixed | Airflow direction |
| AC_FUN_COMODE | Off, Smart, Quiet, Sleep, DlightCool, TurboMode, SoftCool, WindMode1, WindMode2, WindMode3 | Convenient mode |
| AC_FUN_OPERATION | Solo, Couple, Family | Zone operation |
| AC_FUN_SLEEP | 0 (off), 1-420 (minutes) | Sleep timer |
| AC_FUN_ONTIMER | hh:mm or 0 | On timer |
| AC_FUN_OFFTIMER | hh:mm or 0 | Off timer |
| AC_ADD_AUTOCLEAN | On, Off | Auto clean |
| AC_ADD_STERILIZE | On, Off | Sterilize mode |
| AC_ADD_PANEL | Open, Close | Panel position |
| AC_ADD_LIGHT | On, Off | Display light |
| AC_ADD_SMARTON | On, Off | Smart on |
| AC_ADD_VOLUME | Mute, 33, 66, 100 | Beep volume |
| AC_ADD_SETKWH | (number) | Target kWh |
| AC_ADD_SPI | (value) | SPI setting |

### DeviceList
```xml
<Request Type="DeviceList">
  <User StartNum="0" Count="100" GroupID="..." />
</Request>
```

### GetSchedule
```xml
<Request Type="GetSchedule" DUID="DEVICE_UUID"></Request>
```

### SetSchedule
```xml
<Request Type="SetSchedule">
  <ScheduleInfo ScheduleID="id" DaySelection="..." Time="hh:mm" Activate="On|Off">
    <Attr ID="AC_FUN_POWER" Value="On" />
  </ScheduleInfo>
</Request>
```

### DeleteSchedule
```xml
<Request Type="DeleteSchedule">
  <ScheduleInfo ScheduleID="id_to_delete" />
</Request>
```

### ChangeNickname
```xml
<Request Type="ChangeNickname">
  <ChangeNickname DUID="..." Nickname="My AC" />
</Request>
```

### GetRegionCode / SetRegionCode
```xml
<Request Type="GetRegionCode"></Request>

<Request Type="SetRegionCode">
  <RegionCode DUID="..." Code="US" />
</Request>
```

### GetSWInfo
```xml
<Request Type="GetSWInfo"></Request>
```

### GetPowerUsage
```xml
<Request Type="GetPowerUsage">
  <PowerUsage from="2024-01-01 00:00" to="2024-01-31 00:00" Unit="Day" />
</Request>
```
Unit: `Hour`, `Day`
Date format: `yy-MM-dd HH:mm`

### GetPowerLoggingMode / SetPowerLoggingMode
```xml
<Request Type="GetPowerLoggingMode"></Request>

<Request Type="SetPowerLoggingMode" Mode="Enable|Disable"></Request>
```

### ResetPowerLogging
```xml
<Request Type="ResetPowerLogging"></Request>
```

---

## Response XML Formats

### Generic Response
```xml
<Response Type="CommandType" Status="Okay|Fail" ErrorCode="NNN" />
```

### DeviceList Response
```xml
<Response Type="DeviceList" Status="Okay">
  <Device DUID="..." GroupID="..." ModelID="..." />
  <Device DUID="..." GroupID="..." ModelID="..." />
</Response>
```

### DeviceState Response
```xml
<Response Type="DeviceState" Status="Okay">
  <Device DUID="..." GroupID="..." ModelID="..." />
  <Attr ID="AC_FUN_POWER" Type="..." Value="On" />
  <Attr ID="AC_FUN_OPMODE" Type="..." Value="Cool" />
  <Attr ID="AC_FUN_TEMPSET" Type="..." Value="24" />
  <Attr ID="AC_FUN_TEMPNOW" Type="..." Value="25" />
  <Attr ID="AC_FUN_WINDLEVEL" Type="..." Value="Auto" />
  <Attr ID="AC_FUN_DIRECTION" Type="..." Value="Fixed" />
  <Attr ID="AC_FUN_COMODE" Type="..." Value="Off" />
  <Attr ID="AC_FUN_ERROR" Type="..." Value="00000" />
  <Attr ID="AC_ADD2_USEDWATT" Type="..." Value="1234" />
  <Attr ID="AC_OUTDOOR_TEMP" Type="..." Value="80" />
  <!-- ...more Attr elements... -->
</Response>
```

Special value parsing:
- `AC_ADD2_USEDWATT`: Divide by 10.0 for actual kWh
- `AC_OUTDOOR_TEMP`: Subtract 55 for Celsius, clamped 20-40
- `AC_FUN_TEMPSET`: 0 defaults to 24, <8 and !=0 defaults to 16
- `AC_FUN_ERROR`: "00000", "", "00", "0" all mean Normal (no error)
- `AC_ADD2_FILTERTIME`: Values "180", "300", "500", "700" (hours)
- `AC_ADD_VOLUME`: "Mute", "33", "66", "100"

### DeviceControl Response
```xml
<Response Type="DeviceControl" Status="Okay" DUID="..." CommandID="cmd123" />
```

### AuthToken Response
```xml
<Response Type="AuthToken" Status="Okay" StartFrom="2024-01-01T00:00:00" />
```

### GetToken Response
```xml
<Response Type="GetToken" Status="Ready" />
```
Status values: `Ready` (waiting for button press), `Completed` (token issued)

### InvalidateAccount Response
```xml
<Response Type="InvalidateAccount" Status="Okay" ValidRestartPeriod="60" />
```

### GetRegionCode Response
```xml
<Response Type="GetRegionCode" Status="Okay">
  <RegionCode Code="US" />
</Response>
```

### GetSWInfo Response
```xml
<Response Type="GetSWInfo" Status="Okay">
  <SwInfo Version="..." />
  <PannelInfo Version="..." />
  <OutDoorInfo Version="..." />
</Response>
```

### GetPowerUsage Response
```xml
<Response Type="GetPowerUsage" Status="Okay">
  <Usage Date="20240101" Usage="123" Time="12" />
  <Usage Date="20240102" Usage="456" Time="24" />
</Response>
```

### GetPowerLoggingMode Response
```xml
<Response Type="GetPowerLoggingMode" Status="Okay" Mode="Enable" />
```

---

## Push Update Formats (received on port 2848 or 2878)

### Status Update
```xml
<Update Type="Status">
  <Status DUID="..." GroupID="..." ModelID="..." />
  <Attr ID="AC_FUN_POWER" Type="..." Value="On" />
</Update>
```

### InvalidateAccount Update
```xml
<Update Type="InvalidateAccount" Status="Okay|Fail" />
```

### GetToken Update (token delivery)
```xml
<Update Type="GetToken" Status="Completed" Token="TOKEN_VALUE" />
```

---

## Error Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | General Timeout |
| 2 | Socket Timeout |
| 100 | Invalid Parameter |
| 103 | Invalid DUID |
| 105 | Permission Denied |
| 106 | Not Implemented |
| 107 | Invalid Request |
| 109 | Invalid Model ID |
| 111 | Database Access Error |
| 200 | Invalid User ID |
| 201 | Invalid Password |
| 206 | Access Denied |
| 208 | Memory Full |
| 209 | No Account |
| 210 | Cannot Control |
| 211 | Unsupported Function |
| 301 | GetToken Timeout |
| 500 | Internal Error |

---

## Full Attribute ID Reference

### Basic Functions (AC_FUN_*)
| ID | Field | Values |
|----|-------|--------|
| AC_FUN_ENABLE | enable | Enable, Disable |
| AC_FUN_POWER | power | On, Off |
| AC_FUN_OPERATION | operation | Solo, Couple, Family |
| AC_FUN_OPMODE | operationMode | Auto, Cool, Dry, Wind, Heat |
| AC_FUN_COMODE | convenientMode | Off, Smart, Quiet, Sleep, DlightCool, TurboMode, SoftCool, WindMode1/2/3 |
| AC_FUN_WINDLEVEL | windLevel | Auto, Low, Mid, High, Turbo |
| AC_FUN_DIRECTION | windDirection | Off, Indirect, Direct, Center, Wide, Left, Right, Long, SwingUD, SwingLR, Rotation, Fixed |
| AC_FUN_TEMPSET | tempSet | 16-30 |
| AC_FUN_TEMPNOW | tempNow | Current temperature |
| AC_FUN_ONTIMER | onTimer | hh:mm or 0 |
| AC_FUN_OFFTIMER | offTimer | hh:mm or 0 |
| AC_FUN_SLEEP | sleep | 0-420 minutes |
| AC_FUN_ERROR | error | 00000=Normal, else error code |

### Additional Functions (AC_ADD_*)
| ID | Field | Values |
|----|-------|--------|
| AC_ADD_AUTOCLEAN | autoClean | On, Off |
| AC_ADD_STERILIZE | sterilize | On, Off |
| AC_ADD_HUMIDI | humidity | On, Off |
| AC_ADD_PANEL | panel | Open, Close |
| AC_ADD_LIGHT | lighting | On, Off |
| AC_ADD_SMARTON | smartOn | On, Off |
| AC_ADD_WEATHER | weather | (value) |
| AC_ADD_VOLUME | volume | Mute, 33, 66, 100 |
| AC_ADD_SETKWH | setKWH | Target kWh |
| AC_ADD_WIFIMODE | wifiMode | (value) |
| AC_ADD_APMODE_END | apModeEnd | (value) |
| AC_ADD_STARTWPS | startWPS | (value) |
| AC_ADD_WPS_END | wpsEnd | (value) |
| AC_ADD_SPI | spi | (value) |

### Extended Functions (AC_ADD2_*)
| ID | Field | Values |
|----|-------|--------|
| AC_ADD2_USEDWATT | usedWatt | Raw/10.0 = kWh |
| AC_ADD2_OPTIONCODE | optionCode | (hex string) |
| AC_ADD2_FILTERTIME | filterTime | 180, 300, 500, 700 (hours) |
| AC_ADD2_FILTER_USE_TIME | filterUseTime | (hours) |
| AC_ADD2_CLEAR_POWERTIME | clearPowerTime | (value) |

### Outdoor Unit
| ID | Field | Values |
|----|-------|--------|
| AC_OUTDOOR_TEMP | outdoorTemp | Raw-55 = Celsius |
| AC_COOL_CAPABILITY | coolCapability | (value) |
| AC_WARM_CAPABILITY | heatCapability | (value) |

---

## Obfuscation Decryption Reference

The APK uses two string table decryption methods operating on a 143,135-element int[] array:

### aGetDecimalValue(index) — reads backwards
```javascript
function aGetDecimalValue(index) {
  var i2 = table[index];
  var i4 = table[index - 1];
  var len = i4 ^ i2;
  var chars = new Array(len);
  var acc = len, pos = index - 2;
  for (var i = len - 1; i >= 0; i--) {
    acc = (table[pos] - acc) ^ i2;
    chars[i] = String.fromCharCode(acc & 0xFFFF);
    i2 = table[pos];
    pos--;
  }
  return chars.join('');
}
```

### onClickPlayFromSearch(index) — reads forwards
```javascript
function onClickPlayFromSearch(index) {
  var i2 = table[index];
  var i4 = table[index + 1];
  var len = i2 ^ i4;
  var chars = new Array(len);
  var acc = len;
  for (var i = 0; i < len; i++) {
    var val = table[i + index + 2];
    acc = (val - acc) ^ i2;
    i2 = val;
    chars[i] = String.fromCharCode(acc & 0xFFFF);
  }
  return chars.join('');
}
```

### All Decoded Protocol Strings

#### Inline XOR (directly computed in method bodies)
| Decoded | Source | Usage |
|---------|--------|-------|
| `Request` | hAirconControlActivity$13.aAWith() | XML root element for commands |
| `Type` | hAirconControlActivity$13.aGetStream() | Attribute name on Request/Response |
| `On` | hAirconControlActivity$13.dCreateFromParcel() | Power on value |
| `Off` | hAirconControlActivity$13.fXBy() | Power off value |
| `Unknown` | hAirconControlActivity$13.lDefaultImpl() | Fallback state |
| `pm` | hAirconControlActivity$13.eCreateFromParcel() | Schedule time period |
| `DUID` | AirconScheduleTimeSetActivity$16b$3.dFindValuesAsText() | Device unique ID attribute |
| `Mode` | AirconScheduleTimeSetActivity$16b$3.dCompleteAndClearBuffer() | Power logging mode attribute |
| `Nickname` | cModernAsyncTask$WorkerRunnable.writeNumberHasSingleElement() | Device nickname attribute |
| `from` | AirconScheduleTimeSetActivity$15.buildArraySerializerA() | Power usage date-from attribute |
| `to` | AirconScheduleTimeSetActivity$15.buildCollectionSerializerToString() | Power usage date-to attribute |
| `Unit` | AirconScheduleTimeSetActivity$15.buildContainerSerializerB() | Power usage unit type attribute |
| `<Attr ID="#1#" Value="#2#" />` | NopAnnotationIntrospector$1.withAHashCode() | Jungfrau DeviceControl attr template |
| `180` / `300` / `500` / `700` | NopAnnotationIntrospector$1.withValues/Run/etc() | Filter time enum values |
| `EAP` | NopAnnotationIntrospector$1.withC() | WiFi EAP auth type |

#### String Table (aGetDecimalValue / onClickPlayFromSearch)
| Index | Decoded | Usage |
|-------|---------|-------|
| 4777 | `Update` | Response parser: push update root element |
| 4782 | `Response` | Response parser: response root element |
| 11880 | `GroupID` | Device group ID attribute |
| 11986 | `Attr` | Attribute element name |
| 11987 | `ID` | Attr ID attribute name |
| 11991 | `Value` | Attr value attribute name |
| 12111 | `ScheduleInfo` | Schedule element name |
| 12125 | `DaySelection` | Schedule day selection attribute |
| 12139 | `Time` | Schedule time attribute |
| 12145 | `ScheduleID` | Schedule ID attribute |
| 12166 | `Activate` | Schedule activate attribute |
| 12213 | `ChangeNickname` | ChangeNickname element name |
| 12229 | `RegionCode` | Region code element name |
| 12241 | `Code` | Region code attribute |
| 12277 | `Token` | Auth token attribute |
| 12311 | `yy-MM-dd HH:mm` | Power usage date format |
| 12363 | `PowerUsage` | Power usage element name |
| 19972 | `cmd00000` | Default CommandID value |
| 19982 | `Control` | DeviceControl element name |
| 19991 | `CommandID` | Command ID attribute |
| 23971 | `StartNum` | DeviceList start number attribute |
| 23981 | `Count` | DeviceList count attribute |
| 24025 | `User` | User element (for Auth/Token) |
| 24031 | `Password` | Password attribute |
| 29926 | (XML preamble) | Jungfrau XML header string |
| 39132 | `ConnectionConfig` | APConnectionConfig element name |
| 39133 | `SSID` | WiFi SSID attribute |
| 39148 | `AuthMode` | WiFi auth mode attribute |
| 39154 | `Key1` | WiFi password attribute |
| 39167 | `EncryptType` | WiFi encryption type attribute |
| 129729 | `</Control>` | Jungfrau control closing tag |
| 140210 | `<Request Type="` | Jungfrau XML prefix |
| 140227 | `">` | Jungfrau tag closer |
| 140268 | `<Control CommandID="cmd00000" DUID="` | Jungfrau control opener |
| 140280 | `</Request>` | Jungfrau request closer |

---

## Protocol Variants

The APK supports multiple AC models with different protocol variants:

| Variant | Package | Models | Attr ID Style |
|---------|---------|--------|---------------|
| **Jungfrau** | com.samsung.rac.jungfrau | AC14K (AR12HSFSAWKN) | AC_FUN_*, AC_ADD_*, AC_ADD2_* |
| **Venice** | com.samsung.rac.venice | Older models | AC_FUNCTION_*, IDS_AC_FUNCTION_* |
| **Michelangelo** | com.samsung.rac.michelangelo | (other models) | Unknown |
| **Boracay** | com.samsung.rac.boracay | (other models) | Unknown |
| **Crystal** | com.samsung.rac.crystal | (other models) | Unknown |

The AC14K uses the Jungfrau variant. APConnectionConfig is only in the Jungfrau package.
