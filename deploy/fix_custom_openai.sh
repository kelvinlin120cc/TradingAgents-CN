#!/bin/bash
# 修复 custom_openai provider 配置

docker exec tradingagents-mongodb mongosh --eval '
use tradingagents;
db.providers.updateOne(
    { name: "custom_openai" },
    { 
        $set: {
            name: "custom_openai",
            display_name: "自定义OpenAI端点",
            description: "支持任何OpenAI兼容的API端点",
            default_base_url: "https://ark.cn-beijing.volces.com/api/coding/v3",
            is_active: true
        }
    },
    { upsert: true }
);
print("✅ custom_openai 配置已更新");
db.providers.findOne({ name: "custom_openai" });
'
