
-- V1.3--
create table if not exists llm_provider
(
    id                    BIGINT   not null primary key,
    provider_name         VARCHAR(100) null comment 'LLM提供商名称',
    provider_english_name VARCHAR(50)  null comment 'LLM提供商英文名',
    api_key               VARCHAR(100) null,
    base_url              VARCHAR(100) null,
    is_delete             TINYINT default 0 null comment '是否删除, 0: 未删除, 1: 删除',
    create_time           DATETIME null,
    update_time           DATETIME null
) comment 'LLM提供商表';

INSERT INTO llm_provider (id, provider_name, provider_english_name, api_key, base_url, create_time, update_time) VALUES (786254914769649665, '深度求索', 'DeepSeek', 'test', 'https://api.deepseek.com', '2025-12-09 23:36:19', '2025-12-10 22:06:27');
INSERT INTO llm_provider (id, provider_name, provider_english_name, api_key, base_url, create_time, update_time) VALUES (786594449739218945, '火山云', 'ByteDance', 'test', 'https://ark.cn-beijing.volces.com/api/v3', '2025-12-10 22:05:31', '2025-12-10 22:05:31');
INSERT INTO llm_provider (id, provider_name, provider_english_name, api_key, base_url, create_time, update_time) VALUES (786608631641538561, '阿里云', 'ALiYun', 'test', 'https://dashscope.aliyuncs.com/compatible-mode/v1', '2025-12-10 23:01:52', '2025-12-10 23:01:52');
INSERT INTO llm_provider (id, provider_name, provider_english_name, api_key, base_url, create_time, update_time) VALUES (786608813334593537, 'OpenRouter', 'OpenRouter', 'test', 'https://openrouter.ai/api/v1', '2025-12-10 23:02:35', '2025-12-10 23:02:35');
INSERT INTO llm_provider (id, provider_name, provider_english_name, api_key, base_url, create_time, update_time) VALUES (787137527113842688, '硅基流动', 'SiliconCloud', 'test', 'https://api.siliconflow.cn', '2025-12-12 10:03:30', '2025-12-12 10:03:30');

create table if not exists llm_model
(
    id                    BIGINT   not null primary key,
    provider_english_name VARCHAR(50)  null comment 'LLM提供商英文名',
    model_name            VARCHAR(50)  null comment 'LLM模型名称',
    model_id    VARCHAR(50)  null comment 'LLM模型ID',
    billing_unit         VARCHAR(50)  null comment '计费单位',
    input_unit_price      FLOAT null comment 'LLM模型输入单价',
    output_unit_price     FLOAT null comment 'LLM模型输出单价',
    default_params        VARCHAR(500)  null comment '默认模型参数设置',
    status                TINYINT      null comment 'LLM模型状态, 0: 禁用, 1: 启用',
    is_delete             TINYINT default 0 null comment '是否删除, 0: 未删除, 1: 删除',
    create_time           DATETIME null,
    update_time           DATETIME null
) comment 'LLM模型表';

create index llm_model_provider_english_name_index
    on llm_model (provider_english_name);

create index llm_model_status_index
    on llm_model (status);

INSERT INTO llm_model (id, provider_english_name, model_name, model_id, billing_unit, input_unit_price, output_unit_price, status, create_time, update_time) VALUES (786255595048009728, 'DeepSeek', 'deepseek-v3.2', 'deepseek-reasoner', 'per_thousand_tokens', 0.002, 0.003, 1, '2025-12-09 23:39:01', '2025-12-09 23:39:01');




create table if not exists llm_chat_history
(
    id                BIGINT                             not null primary key,
    context           LONGTEXT                            null comment '上下文 json',
    prompt            LONGTEXT                            null,
    answer            LONGTEXT                            null,
    provider_name     VARCHAR(100)                           null comment 'LLM 服务商名称',
    model_name        VARCHAR(50)                            null,
    model_id          VARCHAR(50)                            null,
    api_key_id        INT                             null comment 'API 密钥 ID',
    prompt_tokens     INT      default 0                 null,
    completion_tokens INT      default 0                 null,
    input_price       FLOAT default 0                 null comment '输入价格',
    output_price      FLOAT default 0                 null comment '输出价格',
    ttft_ms           INT      default 0                 null comment '首字延迟（毫秒），流式请求专用',
    create_time       DATETIME default CURRENT_TIMESTAMP null,
    create_day        VARCHAR(10)                           null,
    create_month      VARCHAR(7)                            null,
    create_year       VARCHAR(4)                            null,
    update_time       DATETIME                           null
);

create index llm_chat_history_create_time_index
    on llm_chat_history (create_time);

create index llm_chat_history_create_day_index
    on llm_chat_history (create_day);
create index llm_chat_history_create_month_index
    on llm_chat_history (create_month);
create index llm_chat_history_create_year_index
    on llm_chat_history (create_year);


create index llm_chat_history_model_id_index
    on llm_chat_history (model_id);

create index llm_chat_history_model_name_index
    on llm_chat_history (model_name);

create index llm_chat_history_provider_name_index
    on llm_chat_history (provider_name);

create index llm_chat_history_id_index
    on llm_chat_history (id desc);

create index llm_chat_history_api_key_id_index
    on llm_chat_history (api_key_id);



create table llm_api_keys
(
    api_key_id  int auto_increment primary key,
    api_key     varchar(100)           null,
    remark      varchar(150)           null,
    is_use      tinyint  default 1     null comment '是否可用',
    is_delete   tinyint  default 0     null comment '是否删除',
    create_time datetime default now() null,
    update_time datetime default now() null
)
    comment '接口密钥表';

create index llm_api_keys_api_key_index
    on llm_api_keys (api_key);

create index llm_api_keys_is_use_index
    on llm_api_keys (is_use);

create index llm_api_keys_is_delete_index
    on llm_api_keys (is_delete);

INSERT INTO llm_api_keys (api_key, remark, is_use, is_delete, create_time, update_time) VALUES ('sk-6krzNJoef72vmQkzCAf97BFiMwevu2cQ', null, 1, 0, '2025-12-10 22:08:40', '2025-12-10 22:08:40');



create table if not exists llm_user
(
    id          BIGINT   not null primary key,
    username    VARCHAR(50)  null,
    password    VARCHAR(50)  null,
    is_first_login TINYINT   null comment '是否第一次登录, 0: 否, 1: 是',
    create_time DATETIME default now() null
) comment 'LLM用户表';

create index llm_user_username_index
    on llm_user (username);

create index llm_user_password_index
    on llm_user (password);

INSERT INTO llm_user (id, username, password, is_first_login) VALUES (1, 'stark', '12345678', 1);

-- V1.3--