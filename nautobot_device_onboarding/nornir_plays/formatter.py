"""Command Extraction and Formatting or SSoT Based Jobs."""

import logging
import json
from django.template import engines
from django.utils.module_loading import import_string
from jdiff import extract_data_from_json
from jinja2.sandbox import SandboxedEnvironment


def setup_logger(logger_name, debug_on):
    """Creates a logger for the ETL process."""
    logger = logging.getLogger(logger_name)
    if debug_on:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    return logger


def get_django_env():
    """Load Django Jinja filters from the Django jinja template engine, and add them to the jinja_env.

    Returns:
        SandboxedEnvironment
    """
    # Use a custom Jinja2 environment instead of Django's to avoid HTML escaping
    j2_env = {
        "undefined": "jinja2.StrictUndefined",
        "trim_blocks": True,
        "lstrip_blocks": False,
    }
    if isinstance(j2_env["undefined"], str):
        j2_env["undefined"] = import_string(j2_env["undefined"])
    jinja_env = SandboxedEnvironment(**j2_env)
    jinja_env.filters = engines["jinja"].env.filters
    return jinja_env


def extract_and_post_process(parsed_command_output, yaml_command_element, j2_data_context, iter_type, job_debug):
    """Helper to extract and apply post_processing on a single element."""
    logger = logger = setup_logger("DEVICE_ONBOARDING_ETL_LOGGER", job_debug)
    j2_env = get_django_env()
    jpath_template = j2_env.from_string(yaml_command_element["jpath"])
    j2_rendered_jpath = jpath_template.render(**j2_data_context)
    logger.debug("Post Rendered Jpath: %s", j2_rendered_jpath)
    if parsed_command_output and isinstance(parsed_command_output, str):
        parsed_command_output = json.loads(parsed_command_output)
    try:
        extracted_value = extract_data_from_json(parsed_command_output, j2_rendered_jpath)
    except TypeError as err:
        logger.debug("Error occurred during extraction: %s", err)
        extracted_value = ""
    pre_processed_extracted = extracted_value
    if yaml_command_element.get("post_processor"):
        # j2 context data changes obj(hostname) -> extracted_value for post_processor
        j2_data_context["obj"] = extracted_value
        template = j2_env.from_string(yaml_command_element["post_processor"])
        extracted_processed = template.render(**j2_data_context)
    else:
        extracted_processed = extracted_value
    try:
        post_processed_data = json.loads(extracted_processed)
    except Exception:
        post_processed_data = extracted_processed
    if isinstance(post_processed_data, list) and len(post_processed_data) == 0:
        # means result was empty, change empty result to iterater_type if applicable.
        if iter_type:
            if iter_type == "dict":
                post_processed_data = {}
            if iter_type == "str":
                post_processed_data = ""
    if isinstance(post_processed_data, list) and len(post_processed_data) == 1:
        if isinstance(post_processed_data[0], str):
            post_processed_data = post_processed_data[0]
        else:
            if isinstance(post_processed_data[0], dict):
                if iter_type:
                    if iter_type == "dict":
                        post_processed_data = post_processed_data[0]
            else:
                post_processed_data = post_processed_data[0]
    logger.debug("Pre Processed Extracted: %s", pre_processed_extracted)
    logger.debug("Post Processed Data: %s", post_processed_data)
    return pre_processed_extracted, post_processed_data


def perform_data_extraction(host, command_info_dict, command_outputs_dict, job_debug):
    """Extract, process data."""
    result_dict = {}
    sync_vlans = host.defaults.data.get("sync_vlans", False)
    sync_vrfs = host.defaults.data.get("sync_vrfs", False)
    for ssot_field, field_data in command_info_dict.items():
        if not sync_vlans and ssot_field in ["interfaces__tagged_vlans", "interfaces__untagged_vlan"]:
            continue
        # If syncing vrfs isn't inscope remove the unneeded commands.
        if not sync_vrfs and ssot_field == "interfaces__vrf":
            continue
        if isinstance(field_data["commands"], dict):
            # only one command is specified as a dict force it to a list.
            loop_commands = [field_data["commands"]]
        else:
            loop_commands = field_data["commands"]
        for show_command_dict in loop_commands:
            final_iterable_type = show_command_dict.get("iterable_type")
            if field_data.get("root_key"):
                root_key_pre, root_key_post = extract_and_post_process(
                    command_outputs_dict[show_command_dict["command"]],
                    show_command_dict,
                    {"obj": host.name, "original_host": host.name},
                    final_iterable_type,
                    job_debug,
                )
                # root_key_extracted = a1.copy()
                result_dict[ssot_field] = root_key_post
            else:
                field_nesting = ssot_field.split("__")
                # for current_nesting in field_nesting:
                if len(field_nesting) > 1:
                    # Means there is "anticipated" data nesting `interfaces__mtu` means final data would be
                    # {"Ethernet1/1": {"mtu": <value>}}
                    for current_key in root_key_pre:
                        # current_key is a single iteration from the root_key extracted value. Typically we want this to be
                        # a list of data that we want to become our nested key. E.g. current_key "Ethernet1/1"
                        # These get passed into the render context for the template render to allow nested jpaths to use
                        # the current_key context for more flexible jpath queries.
                        _, current_key_post = extract_and_post_process(
                            command_outputs_dict[show_command_dict["command"]],
                            show_command_dict,
                            {"current_key": current_key, "obj": host.name, "original_host": host.name},
                            final_iterable_type,
                            job_debug,
                        )
                        result_dict[field_nesting[0]][current_key][field_nesting[1]] = current_key_post
                else:
                    _, current_field_post = extract_and_post_process(
                        command_outputs_dict[show_command_dict["command"]],
                        show_command_dict,
                        {"obj": host.name, "original_host": host.name},
                        final_iterable_type,
                        job_debug,
                    )
                    result_dict[ssot_field] = current_field_post
        # if command_info_dict.get("validator_pattern"):
        #     # temp validator
        #     if command_info_dict["validator_pattern"] == "not None":
        #         if not extracted_processed:
        #             logger.debug("validator pattern not detected, checking next command.")
        #             continue
        #         else:
        #             logger.debug("About to break the sequence due to valid pattern found")
        #             result_dict[dict_field] = extracted_processed
        #             break
    return result_dict


def extract_show_data(host, command_outputs, command_getter_type, job_debug):
    """Take a result of show command and extra specific needed data.

    Args:
        host (host): host from task
        command_outputs (dict): dictionary of results from command getter.
        command_getter_type (str): to know what dict to pull, sync_devices or sync_network_data.
        job_debug (logging.INFO or logging.DEBUG): to know if debug button was checked.
    """
    command_getter_iterable = host.data["platform_parsing_info"][command_getter_type]
    all_results_extracted = perform_data_extraction(host, command_getter_iterable, command_outputs, job_debug)
    return all_results_extracted
