# NODEBLE Emergency Runbook

**Audience**: Non-technical users running NODEBLE on their own Vultr VPS.
**Purpose**: Step-by-step actions for the 8 most common emergency situations.

> When in doubt, enable the kill switch first (Scenario 1), then read the rest.

---

## Scenario 1 — Kill Switch: Stop the Bot From Placing New Trades

### What's happening
You want to prevent the bot from opening any new positions immediately — for example, the market is behaving strangely or you just want to pause trading.

### What to do

**Option A — Edit the config file (always works):**

1. Open a terminal and SSH into your VPS.
2. Run:
   ```
   nano ~/.nodeble/config/risk.yaml
   ```
3. Find the line that says `kill_switch: false` and change it to:
   ```
   kill_switch: true
   ```
4. Save: press `Ctrl+O`, then `Enter`, then `Ctrl+X`.
5. The next time the bot runs, it will see this setting and skip all new trades.

**Option B — Send a Telegram message (fastest, if your Telegram bot is set up):**

1. Open Telegram and go to your NODEBLE bot chat.
2. Send the message:
   ```
   /kill
   ```
3. The bot will confirm the kill switch is active.

**Important**: The kill switch stops NEW trades only. Any positions that are already open will continue to be managed normally (profit targets, stop losses, and expiry closes still run). This is intentional — the bot will not abandon open positions.

---

## Scenario 2 — VPS Down / Bot Not Running

### What's happening
You stopped receiving Telegram updates, or you suspect the bot has not run on schedule. The VPS may be down, or the scheduled task (cron) may have stopped.

### What to do

**Step 1 — Check whether the cron job is registered:**
```
crontab -l | grep nodeble
```
You should see one or more lines showing the bot's scheduled times. If nothing appears, the cron job was removed — contact the founder to reinstall it.

**Step 2 — Check when the bot last ran:**
```
tail ~/.nodeble/logs/cron.log
```
This shows the last few lines from the bot's scheduled run log. Look for a recent timestamp. If the last entry is hours or days old, the bot has not been running.

**Step 3 — Run the bot manually to test (safe, dry-run mode):**
```
cd ~/nodeble && .venv/bin/python -m nodeble --mode scan --dry-run --force
```
This runs a full scan cycle but makes no real trades. It will print what it would do and alert you to any errors.

**Step 4 — If the VPS itself is unreachable:**
1. Log in to your Vultr account at [vultr.com](https://vultr.com).
2. Go to your server, click "View Console" to open a browser terminal.
3. If the server is frozen, click "Restart" (or "Power Cycle" if restart does not work).
4. Once it comes back, SSH in normally and re-run Step 3 to confirm the bot is working.

---

## Scenario 3 — Partial Fill / Incomplete Position

### What's happening
The bot tried to open an iron condor but one or more of the four legs did not fill completely. The position is in an incomplete state — some legs are open, some may not be.

### What to do

**Step 1 — Do nothing immediately.** On the next scheduled manage cycle, the bot will automatically call `verify_pending_fills()` and detect the incomplete state. It will handle it according to its built-in rules.

**Step 2 — Check the current state file to see what the bot recorded:**
```
cat ~/.nodeble/data/state.json | python3 -m json.tool
```
Look for any position with a status of `pending`. That is the incomplete one.

**Step 3 — Wait for the next cycle.** If the position is still showing `pending` after two or three scheduled cycles (usually 30–60 minutes), contact the founder and share the output from Step 2.

**Do NOT manually edit `state.json`.** The file uses a specific format and locking mechanism. Manual edits can corrupt the state and cause the bot to behave unpredictably. The founder can make safe corrections via SSH if needed.

---

## Scenario 4 — Unwanted Position Opened

### What's happening
The bot opened a position you did not expect or do not want — for example, it opened on a symbol you thought was excluded, or the market moved significantly right after entry.

### What to do

**Step 1 — Enable the kill switch first** (see Scenario 1) to prevent any additional positions from opening.

**Step 2 — Do not panic.** The position is now being managed normally by the bot. It will close at the profit target, stop loss, or DTE (days-to-expiry) threshold — whichever comes first. These rules are already set in your config.

**Step 3 — If you need the position closed immediately:**
This is not yet a self-service feature. Contact the founder, who will SSH into your VPS and run a manual close command. Do not try to close it yourself through the broker app while the bot is running, as this can create a mismatch between the broker's state and the bot's state file.

---

## Scenario 5 — Tiger API Down / Connection Errors

### What's happening
Tiger Brokers' API is temporarily unavailable or returning errors. The bot cannot connect to check positions or place trades.

### What to do

**Nothing — the bot handles this automatically.**

- The bot will retry the connection once.
- If it still fails, it will send you a Telegram alert describing the error.
- It will then exit the current cycle cleanly — no positions will be modified, no partial actions taken.
- The bot will try again on the next scheduled run.

**You do not need to restart the bot or touch any files.** Simply wait for Tiger's API to recover. You can check Tiger's status in the Tiger Trade app or on their website.

If the outage lasts more than a few hours and you have open positions approaching expiry, contact the founder.

---

## Scenario 6 — Credential Rotation: Update Your Tiger API Key

### What's happening
Tiger Brokers issued you a new API key, or you rotated your credentials for security reasons. The bot needs to use the new credentials.

### What to do

**Step 1 — Update the broker config file:**
```
nano ~/.nodeble/config/broker.yaml
```
Update the relevant fields (Tiger ID, account number, or key path) with your new values. Save with `Ctrl+O`, `Enter`, `Ctrl+X`.

**Step 2 — Replace the private key file:**
Copy your new private key file to:
```
~/.nodeble/config/tiger_private_key.pem
```
Then set the correct permissions so only your user can read it:
```
chmod 600 ~/.nodeble/config/tiger_private_key.pem
```

**Step 3 — Test the connection:**
```
cd ~/nodeble && .venv/bin/python -m nodeble --test-broker
```
You should see a success message confirming the bot can connect with the new credentials.

**No restart is needed.** The bot reads the config file fresh on every scheduled run, so the next cron execution will automatically use the new credentials.

---

## Scenario 7 — Margin Call / Forced Liquidation

### What's happening
Tiger Brokers has determined your account does not have enough margin to hold your current positions. They may close positions on your behalf without warning. This is a broker action, not a bot action.

### What to do

**Step 1 — Enable the kill switch immediately** (see Scenario 1). This stops the bot from opening any new positions while you deal with the margin situation.

**Step 2 — Check your margin status** in the Tiger Trade app or on the Tiger web platform. Look at your available margin and which positions are flagged.

**Step 3 — Resolve the margin issue** using one of these methods (in the Tiger Trade app, not through the bot):
- Deposit additional funds into your Tiger account.
- Manually close one or more positions to free up margin.

**Step 4 — Contact the founder** to let them know what happened. They will check the bot's state file to make sure it is consistent with what the broker now shows, and re-sync if needed.

**After the situation is resolved**, disable the kill switch (`kill_switch: false` in `risk.yaml`) to allow the bot to resume normal trading.

---

## Scenario 8 — deploy.sh Failures: Common Setup Errors

### What's happening
You are running the deployment script for the first time (or re-running it after a reset) and it is failing at one of the setup steps.

### What to do

**Error: Python not found or wrong version**
```
sudo apt install python3.12 python3.12-venv
```
Then re-run `deploy.sh`.

**Error: Permission denied on the private key file**
The private key file must not be readable by other users. Fix it with:
```
chmod 600 ~/.nodeble/config/tiger_private_key.pem
```

**Error: Broker connection test fails**
Open the broker config and double-check every field:
```
nano ~/.nodeble/config/broker.yaml
```
Common mistakes: a space before or after the Tiger ID, the wrong account number format, or the private key path pointing to the wrong file. Compare carefully against the values from your Tiger Developer portal.

**Error: Cron job not running after setup**
Check whether the cron job was registered:
```
crontab -l
```
If you do not see NODEBLE entries, the cron installation step in `deploy.sh` may have failed silently. Contact the founder and share the full output of `deploy.sh`.

---
---
---

# NODEBLE 紧急操作手册

**目标读者**：在自己的 Vultr VPS 上运行 NODEBLE 的非技术用户。
**用途**：针对 8 种最常见紧急情况的逐步操作指南。

> 遇到问题时，先开启急停开关（情境 1），再阅读其他内容。

---

## 情境 1 — 急停开关：立即阻止机器人开新仓

### 发生了什么
你想立刻阻止机器人开新仓位——例如市场走势异常，或者你只是想暂停交易。

### 操作步骤

**方式 A — 修改配置文件（始终有效）：**

1. 打开终端，通过 SSH 登录你的 VPS。
2. 运行：
   ```
   nano ~/.nodeble/config/risk.yaml
   ```
3. 找到 `kill_switch: false` 这一行，将其改为：
   ```
   kill_switch: true
   ```
4. 保存：按 `Ctrl+O`，再按 `Enter`，再按 `Ctrl+X`。
5. 机器人下次运行时会读取此设置，跳过所有新交易。

**方式 B — 发送 Telegram 消息（最快，需已配置 Telegram 机器人）：**

1. 打开 Telegram，进入你的 NODEBLE 机器人对话。
2. 发送消息：
   ```
   /kill
   ```
3. 机器人会回复确认急停开关已激活。

**重要说明**：急停开关只阻止开新仓。已有的持仓仍会正常管理（止盈、止损、临近到期平仓照常执行）。这是刻意设计的——机器人不会丢弃已有持仓。

---

## 情境 2 — VPS 宕机 / 机器人未运行

### 发生了什么
你停止收到 Telegram 通知，或怀疑机器人没有按计划运行。可能是 VPS 宕机，或定时任务（cron）已停止。

### 操作步骤

**第 1 步 — 检查定时任务是否已注册：**
```
crontab -l | grep nodeble
```
正常情况下应显示一行或多行机器人的定时计划。如果没有任何输出，说明定时任务被删除了——请联系创始人重新安装。

**第 2 步 — 查看机器人最近一次运行时间：**
```
tail ~/.nodeble/logs/cron.log
```
显示机器人定时运行日志的最后几行。查看最近的时间戳。如果最后一条记录是几小时甚至几天前，说明机器人一直没有运行。

**第 3 步 — 手动测试运行机器人（安全，模拟模式）：**
```
cd ~/nodeble && .venv/bin/python -m nodeble --mode scan --dry-run --force
```
这会执行一次完整的扫描流程，但不会产生真实交易。它会打印机器人将执行的操作，并报告任何错误。

**第 4 步 — 如果 VPS 本身无法访问：**
1. 登录你的 Vultr 账户，网址：[vultr.com](https://vultr.com)。
2. 进入你的服务器，点击"View Console"打开浏览器终端。
3. 如果服务器卡死，点击"Restart"（如果不行则点"Power Cycle"）。
4. 服务器恢复后，正常 SSH 登录，然后重新执行第 3 步，确认机器人工作正常。

---

## 情境 3 — 部分成交 / 仓位不完整

### 发生了什么
机器人尝试开一个铁鹰式期权组合，但四条腿中有一条或多条没有完全成交。仓位处于不完整状态。

### 操作步骤

**第 1 步 — 暂时不要操作。** 在下一次计划的管理周期中，机器人会自动调用 `verify_pending_fills()`，检测到不完整状态，并按内置规则处理。

**第 2 步 — 查看当前状态文件，了解机器人记录了什么：**
```
cat ~/.nodeble/data/state.json | python3 -m json.tool
```
查找状态为 `pending` 的仓位，那就是不完整的仓位。

**第 3 步 — 等待下一个周期。** 如果经过两三个计划周期（通常 30–60 分钟）后仓位仍显示 `pending`，请联系创始人，并分享第 2 步的输出内容。

**请不要手动编辑 `state.json`。** 该文件使用特定格式和文件锁机制。手动编辑可能损坏状态，导致机器人行为异常。如有必要，创始人可以通过 SSH 安全地进行修正。

---

## 情境 4 — 开了不想要的仓位

### 发生了什么
机器人开了一个你没预期到或不希望开的仓位——例如在你以为已排除的标的上建仓，或者入场后市场大幅波动。

### 操作步骤

**第 1 步 — 先开启急停开关**（参见情境 1），防止再开更多仓位。

**第 2 步 — 保持冷静。** 该仓位现在由机器人正常管理，将在达到止盈目标、止损线或 DTE（距到期天数）阈值时平仓，以最先触发者为准。这些规则已在你的配置中设定好。

**第 3 步 — 如果需要立即强制平仓：**
这项功能目前尚不支持自助操作。请联系创始人，他会通过 SSH 登录你的 VPS 并执行手动平仓命令。在机器人运行期间，请不要自行通过券商 App 平仓，否则可能导致券商账户状态与机器人状态文件不一致。

---

## 情境 5 — Tiger API 宕机 / 连接错误

### 发生了什么
老虎证券的 API 暂时不可用或返回错误。机器人无法连接以查询持仓或下单。

### 操作步骤

**无需操作——机器人会自动处理。**

- 机器人会重试连接一次。
- 如果仍然失败，会向你发送 Telegram 警报，说明错误原因。
- 然后它会干净地退出本次运行周期——不会修改任何仓位，也不会执行不完整的操作。
- 在下一次计划运行时，机器人会再次尝试。

**你不需要重启机器人或修改任何文件。** 只需等待老虎证券 API 恢复。你可以在 Tiger Trade App 或老虎网站上查看服务状态。

如果故障持续数小时，且你有仓位即将到期，请联系创始人。

---

## 情境 6 — 凭证更换：更新 Tiger API 密钥

### 发生了什么
老虎证券为你签发了新的 API 密钥，或者你出于安全原因轮换了凭证。机器人需要使用新的凭证。

### 操作步骤

**第 1 步 — 更新券商配置文件：**
```
nano ~/.nodeble/config/broker.yaml
```
将相关字段（Tiger ID、账户号码或密钥路径）更新为新值。按 `Ctrl+O`、`Enter`、`Ctrl+X` 保存。

**第 2 步 — 替换私钥文件：**
将新的私钥文件复制到：
```
~/.nodeble/config/tiger_private_key.pem
```
然后设置正确的权限，确保只有你的用户可以读取：
```
chmod 600 ~/.nodeble/config/tiger_private_key.pem
```

**第 3 步 — 测试连接：**
```
cd ~/nodeble && .venv/bin/python -m nodeble --test-broker
```
应显示成功消息，确认机器人可以使用新凭证连接。

**无需重启机器人。** 机器人每次运行时都会重新读取配置文件，因此下一次定时任务执行时会自动使用新凭证。

---

## 情境 7 — 追加保证金通知 / 强制平仓

### 发生了什么
老虎证券判定你的账户没有足够的保证金来维持当前持仓。他们可能会在不通知你的情况下强制平仓。这是券商的操作，不是机器人的操作。

### 操作步骤

**第 1 步 — 立即开启急停开关**（参见情境 1），阻止机器人在你处理保证金问题期间继续开新仓。

**第 2 步 — 在 Tiger Trade App 或老虎网页端查看保证金状态。** 查看可用保证金和被标记的仓位。

**第 3 步 — 在 Tiger Trade App 中解决保证金问题**（不要通过机器人操作）：
- 向老虎账户追加资金。
- 手动平仓一个或多个仓位以释放保证金。

**第 4 步 — 联系创始人**，告知发生了什么。他会检查机器人状态文件，确保其与券商当前显示的状态一致，必要时进行同步。

**情况解决后**，在 `risk.yaml` 中将 `kill_switch` 改回 `false`，让机器人恢复正常交易。

---

## 情境 8 — deploy.sh 安装脚本失败：常见错误

### 发生了什么
你在首次运行部署脚本（或重置后重新运行）时，某个步骤出现了失败。

### 操作步骤

**错误：找不到 Python 或版本不对**
```
sudo apt install python3.12 python3.12-venv
```
然后重新运行 `deploy.sh`。

**错误：私钥文件权限不足**
私钥文件不能被其他用户读取。用以下命令修复：
```
chmod 600 ~/.nodeble/config/tiger_private_key.pem
```

**错误：券商连接测试失败**
打开券商配置文件，仔细核对每个字段：
```
nano ~/.nodeble/config/broker.yaml
```
常见错误：Tiger ID 前后有空格、账户号码格式不正确、或私钥路径指向了错误的文件。请对照老虎证券开发者平台上的信息逐项核查。

**错误：安装后定时任务不运行**
检查定时任务是否已注册：
```
crontab -l
```
如果没有看到 NODEBLE 相关条目，说明 `deploy.sh` 中的 cron 安装步骤可能已静默失败。请联系创始人，并提供 `deploy.sh` 的完整输出内容。
