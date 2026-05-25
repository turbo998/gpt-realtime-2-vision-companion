# Deployment Runbook

End-to-end deploy on Azure with **minimum cost** (Container Apps consumption scale-to-zero + SWA Free + pay-as-you-go AOAI).

## 0. 一次性准备（已在本机做好）

- [x] `azd` v1.25+ 已安装：`/usr/local/bin/azd`
- [x] `az` CLI v2.86+ 已安装
- [x] 仓库已 clone 在 `~/gpt-realtime-2-vision-companion`
- [x] Bicep 通过 `az bicep build` 校验

明天还需要做的：

- [ ] **docker** 装好（azd 用它构建后端镜像）：`sudo apt-get update && sudo apt-get install -y docker.io && sudo usermod -aG docker azureuser` → 重新登录
- [ ] 登录 qichen2@microsoft.com（详见步骤 1）

## 1. 登录

```bash
# Azure CLI（用于 bicep 部署的底层调用）
az login --use-device-code
# 浏览器打开返回的 URL，输入 device code，账号选 qichen2@microsoft.com
az account set --subscription "<目标订阅名或 ID>"
az account show --query "{user:user.name,sub:name,id:id}" -o table

# Azure Developer CLI（azd 走自己的 token 缓存）
azd auth login --use-device-code
```

> ⚠️ 企业租户可能要求 MFA + conditional access。如果 device code 被拦，要么换浏览器登录，要么找 IT 加白名单。

## 2. 初始化 azd 环境

```bash
cd ~/gpt-realtime-2-vision-companion
azd env new vc-prod
# 设区域（已有默认值，可不改）
azd env set AZURE_LOCATION southeastasia          # Container App + 监控
azd env set AZURE_OPENAI_LOCATION japaneast       # gpt-realtime-2 在新加坡没有
azd env set AZURE_SWA_LOCATION eastasia           # SWA Free 在新加坡没有，香港最近
azd env set ALLOWED_ORIGINS "*"                   # demo 阶段先放开；生产收紧到 SWA 域
```

## 3. 部署

```bash
# 一条命令：provision (创资源) + build (打镜像) + deploy (推服务)
azd up
```

期间会提示：
- 选订阅 → qichen2 那个
- 选 region（已通过 env 预设，回车确认即可）
- 创建/选已有 RG → 建新的 `rg-vc-prod`

**首次 provision** 用 placeholder 镜像（`mcr.microsoft.com/k8se/quickstart`）启 Container App，azd 紧接着会自动 build 你的镜像、推 ACR、滚动更新。

**postprovision hook 自动执行** `scripts/inject-config.sh`，把 `BACKEND_URL` 写进 `frontend/src/config.js`，前端就能找到后端 WSS。

## 4. 验收

```bash
# 看输出
azd env get-values | grep -E "FRONTEND_URL|BACKEND_URL|AZURE_OPENAI_ENDPOINT"

# 后端 healthcheck
curl "$(azd env get-value BACKEND_URL)/health"

# 浏览器打开前端
xdg-open "$(azd env get-value FRONTEND_URL)"   # macOS: open
```

页面流程：
1. 看到右上角 "stub" 红角 → 检查 Container App 日志：`az containerapp logs show -g rg-vc-prod -n vc-prod-backend --follow`
2. 看到右上角 "gpt-realtime-2" 绿角 → 点开始 → 授权麦克风/摄像头 → 按 `docs/demo-script.md` 走

## 5. 成本控制

| 资源 | 默认 SKU | 闲置成本 | 活跃成本 |
|---|---|---|---|
| Container Apps (consumption) | min=0 max=1 | $0 | $0.000024/vCPU·s |
| Static Web App | Free | $0 | $0 |
| Container Registry | Basic | ~$0.17/天 | 同上 |
| Log Analytics + App Insights | PerGB | $0 | ~$2.3/GB |
| Azure OpenAI gpt-realtime-2 | GlobalStandard | $0 | $32/M in, $64/M out tokens |

**闲置一天约 $0.20**（主要是 ACR Basic）。

### 完全停摆
```bash
az containerapp update -g rg-vc-prod -n vc-prod-backend --min-replicas 0 --max-replicas 0
```

### 拆光重来
```bash
azd down --purge --force
```

> `--purge` 会把 AOAI 账号也彻底删除（避免软删除占名额）。

## 6. 故障排查

| 症状 | 原因 | 解决 |
|---|---|---|
| `azd provision` 报 `realtime` deployment not available | gpt-realtime-2 不在该 region | 改 `AZURE_OPENAI_LOCATION=eastus2` 或 `swedencentral` |
| 前端 console: WSS 连不上 | `__BACKEND__` 没注入 / CORS / WSS 协议升级失败 | 检查 `frontend/src/config.js`、Container App ingress 必须 `external=true` `transport=auto` |
| Container App 一直 stub mode | UAMI 没绑 OpenAI 账户角色 | `az role assignment list --assignee <UAMI clientId>`，应有 `Cognitive Services OpenAI User` |
| 首句延迟 >1.5s | 跨大区 RTT 高 | 把 Container App 也迁到 japaneast；或换 swedencentral 一站式 |
| docker push 慢 | ACR Basic 限速 | 升 Standard 或忍 |

## 7. 后续 CI/CD（可选）

```bash
azd pipeline config
```

会自动在 GitHub 仓库创建 OIDC federated credential + workflow（`.github/workflows/azure-dev.yml`），push to main → 自动 `azd deploy`。
