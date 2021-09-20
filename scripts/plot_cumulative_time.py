#!/usr/bin/env python3
# Copyright 2021 Christophe Bedard
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Plot cumulative time based on daily time reporting data."""

from typing import List
from typing import Optional
from typing import Union

from datetime import date
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd


include_plot_title = True
save_plots = True


def load_csv(filename: str) -> np.array:
    with open(filename, 'rb') as file:
        return np.loadtxt(
            file,
            delimiter=',',
            skiprows=1,
            usecols=(0,1),
            dtype=str,
        )


def filter_data(data: np.array) -> np.array:
    return np.array([d for d in data if d[0] not in ('', 'total')])


def convert_data(data: np.array) -> np.array:
    return np.array([[date.fromisoformat(d[0]), float(d[1])] for d in data])


def add_zeroth_datapoint(data: np.array) -> np.array:
    return np.vstack([[[data[0,0], 0.0]], data])


def data_to_cumsum(data: np.array, col: int = 1) -> np.array:
    data[:,col] = np.cumsum(data[:,col])
    return data


def get_data(filename: str):
    data = load_csv(filename)
    data = filter_data(data)
    data = convert_data(data)
    data = add_zeroth_datapoint(data)
    data = data_to_cumsum(data)
    return data


def format_filename(string: str) -> str:
    string = string.replace('(', '')
    string = string.replace(')', '')
    string = string.replace(' ', '_')
    string = string.replace('\\', '')
    return string.lower()


def plot_data(
    data: np.array,
    title: str,
    major_formatter_str: str,
    major_locator: Optional[mdates.RRuleLocator] = None,
    yaxis_multiple_locator: Optional[int] = None,
    colour: str = 'blue',
) -> None:
    fig, ax = plt.subplots(1, 1)

    ax.plot(data[:,0], data[:,1], '-', color=colour)

    if include_plot_title:
        ax.set(title=title)
    ax.set(ylabel='cumulative time (h)')
    if major_locator:
        ax.xaxis.set_major_locator(major_locator)
    ax.xaxis.set_major_formatter(mdates.DateFormatter(major_formatter_str))
    if yaxis_multiple_locator:
        ax.yaxis.set_major_locator(ticker.MultipleLocator(yaxis_multiple_locator))
    ax.set_ylim(0)
    ax.grid()
    fig.autofmt_xdate()

    if save_plots:
        filename = format_filename(title)
        fig.savefig(f'{filename}.png', bbox_inches='tight')
        fig.savefig(f'{filename}.svg', bbox_inches='tight')


def plot_data_compare(
    data: List[np.array],
    title: str,
    legends: List[str],
    major_formatter_str: str,
    major_locator: Optional[mdates.RRuleLocator] = None,
    yaxis_multiple_locator: Optional[int] = None,
    colours: Union[str, List[str]] = 'blue',
) -> None:
    fig, ax = plt.subplots(1, 1)

    for i in range(len(data)):
        colour = colours if isinstance(colours, str) else colours[i]
        d = data[i]
        ax.plot(d[:,0], d[:,1], '-', color=colour)
        total_time = d[-1,1]
        legends[i] = legends[i] + f' ({total_time:g} h)'

    if include_plot_title:
        ax.set(title=title)
    ax.set(ylabel='cumulative time (h)')
    if major_locator:
        ax.xaxis.set_major_locator(major_locator)
    ax.xaxis.set_major_formatter(mdates.DateFormatter(major_formatter_str))
    if yaxis_multiple_locator:
        ax.yaxis.set_major_locator(ticker.MultipleLocator(yaxis_multiple_locator))
    ax.set_ylim(0)
    ax.legend(legends)#, loc='center', bbox_to_anchor=(0.3, 0.8))
    ax.grid()
    fig.autofmt_xdate()

    if save_plots:
        filename = format_filename(title)
        fig.savefig(f'{filename}.png', bbox_inches='tight')
        fig.savefig(f'{filename}.svg', bbox_inches='tight')


def main():
    plt.rc('text', usetex=True)
    plt.rc('font', family='serif', size=14)
    plt.rc('axes', titlesize=20)
    plt.rc('legend', fontsize=14)

    # Under File, Download -> Comma-separated values (.csv, current sheet),
    # download the 'Time' and 'Blog' sheets
    data_time = get_data('rmw_email time tracking - Code.csv')
    data_blog = get_data('rmw_email time tracking - Blog.csv')

    plot_data(
        data_time,
        'rmw\_email code time investment',
        '%Y %B',
        colour='green',
    )
    plot_data(
        data_blog,
        'rmw\_email blog post time investment',
        '%Y-%b-%d',
        mdates.DayLocator((1,5,10,15,20,25)),
        yaxis_multiple_locator=5,
        colour='blue',
    )

    plot_data_compare(
        [data_time, data_blog],
        'Overall rmw\_email time investment',
        ['code', 'blog post'],
        '%Y %B',
        colours=['green', 'blue'],
    )

    plt.show()


if __name__ == '__main__':
    main()
